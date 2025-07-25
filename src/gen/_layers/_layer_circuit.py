import dataclasses
from typing import TypeVar, Type, cast, Literal

import stim

from gen._layers._det_obs_annotation_layer import DetObsAnnotationLayer
from gen._layers._empty_layer import EmptyLayer
from gen._layers._feedback_layer import FeedbackLayer
from gen._layers._interact_layer import InteractLayer
from gen._layers._interact_swap_layer import InteractSwapLayer
from gen._layers._iswap_layer import ISwapLayer
from gen._layers._layer import Layer
from gen._layers._loop_layer import LoopLayer
from gen._layers._measure_layer import MeasureLayer
from gen._layers._mpp_layer import MppLayer
from gen._layers._noise_layer import NoiseLayer
from gen._layers._qubit_coord_annotation_layer import QubitCoordAnnotationLayer
from gen._layers._reset_layer import ResetLayer
from gen._layers._rotation_layer import RotationLayer
from gen._layers._shift_coord_annotation_layer import ShiftCoordAnnotationLayer
from gen._layers._sqrt_pp_layer import SqrtPPLayer
from gen._layers._swap_layer import SwapLayer

TLayer = TypeVar("TLayer")


@dataclasses.dataclass
class LayerCircuit:
    layers: list[Layer] = dataclasses.field(default_factory=list)

    def touched(self) -> set[int]:
        result = set()
        for layer in self.layers:
            result |= layer.touched()
        return result

    def copy(self) -> "LayerCircuit":
        return LayerCircuit(layers=[e.copy() for e in self.layers])

    def to_z_basis(self) -> "LayerCircuit":
        result = LayerCircuit()
        for layer in self.layers:
            result.layers.extend(layer.to_z_basis())
        return result

    def _feed(self, kind: Type[TLayer]) -> TLayer:
        if not self.layers:
            self.layers.append(kind())
        elif isinstance(self.layers[-1], EmptyLayer):
            self.layers[-1] = kind()
        elif not isinstance(self.layers[-1], kind):
            self.layers.append(kind())
        return self.layers[-1]

    def _feed_reset(
        self, basis: Literal["X", "Y", "Z"], targets: list[stim.GateTarget]
    ):
        layer = self._feed(ResetLayer)
        for t in targets:
            layer.targets[t.value] = basis

    def _feed_m(self, basis: Literal["X", "Y", "Z"], targets: list[stim.GateTarget]):
        layer = self._feed(MeasureLayer)
        for t in targets:
            layer.bases.append(basis)
            layer.targets.append(t.value)

    def _feed_mpp(self, targets: list[stim.GateTarget]):
        layer = self._feed(MppLayer)
        start = 0
        end = 1
        while start < len(targets):
            while end < len(targets) and targets[end].is_combiner:
                end += 2
            layer.targets.append(targets[start:end:2])
            start = end
            end += 1

    def _feed_qubit_coords(
        self, targets: list[stim.GateTarget], gate_args: list[float]
    ):
        layer = self._feed(QubitCoordAnnotationLayer)
        for target in targets:
            assert target.is_qubit_target
            q = target.value
            if q in layer.coords:
                raise ValueError(f"Qubit coords specified twice for {q}")
            layer.coords[q] = list(gate_args)

    def _feed_shift_coords(self, gate_args: list[float]):
        self._feed(ShiftCoordAnnotationLayer).offset_by(gate_args)

    def _feed_named_rotation_instruction(self, instruction: stim.CircuitInstruction):
        layer = self._feed(RotationLayer)
        name = instruction.name
        for t in instruction.targets_copy():
            layer.append_named_rotation(name, t.value)

    def _feed_swap(self, targets: list[stim.GateTarget]):
        layer = self._feed(SwapLayer)
        for k in range(0, len(targets), 2):
            layer.targets1.append(targets[k].value)
            layer.targets2.append(targets[k + 1].value)

    def _feed_cxswap(self, targets: list[stim.GateTarget]):
        layer = self._feed(InteractSwapLayer)
        for k in range(0, len(targets), 2):
            layer.i_layer.targets1.append(targets[k].value)
            layer.i_layer.targets2.append(targets[k + 1].value)
            layer.i_layer.bases1.append("Z")
            layer.i_layer.bases2.append("X")
            layer.swap_layer.targets1.append(targets[k].value)
            layer.swap_layer.targets2.append(targets[k + 1].value)

    def _feed_swapcx(self, targets: list[stim.GateTarget]):
        layer = self._feed(InteractSwapLayer)
        for k in range(0, len(targets), 2):
            layer.i_layer.targets1.append(targets[k].value)
            layer.i_layer.targets2.append(targets[k + 1].value)
            layer.i_layer.bases1.append("X")
            layer.i_layer.bases2.append("Z")
            layer.swap_layer.targets1.append(targets[k].value)
            layer.swap_layer.targets2.append(targets[k + 1].value)

    def _feed_iswap(self, targets: list[stim.GateTarget]):
        layer = self._feed(ISwapLayer)
        for k in range(0, len(targets), 2):
            layer.targets1.append(targets[k].value)
            layer.targets2.append(targets[k + 1].value)

    def _feed_sqrt_pp(
        self, basis: Literal["X", "Y", "Z"], targets: list[stim.GateTarget]
    ):
        layer = self._feed(SqrtPPLayer)
        for k in range(0, len(targets), 2):
            layer.targets1.append(targets[k].value)
            layer.targets2.append(targets[k + 1].value)
            layer.bases.append(basis)

    def _feed_c(
        self,
        basis1: Literal["X", "Y", "Z"],
        basis2: Literal["X", "Y", "Z"],
        targets: list[stim.GateTarget],
    ):
        is_feedback = any(
            t.is_sweep_bit_target or t.is_measurement_record_target for t in targets
        )
        if is_feedback:
            layer = self._feed(FeedbackLayer)
            for k in range(0, len(targets), 2):
                c = targets[k]
                t = targets[k + 1]
                if t.is_sweep_bit_target or t.is_measurement_record_target:
                    c, t = t, c
                    layer.bases.append(basis1)
                else:
                    layer.bases.append(basis2)
                layer.controls.append(c)
                layer.targets.append(t.value)
        else:
            layer = self._feed(InteractLayer)
            for k in range(0, len(targets), 2):
                layer.bases1.append(basis1)
                layer.bases2.append(basis2)
                layer.targets1.append(targets[k].value)
                layer.targets2.append(targets[k + 1].value)

    @staticmethod
    def from_stim_circuit(circuit: stim.Circuit) -> "LayerCircuit":
        result = LayerCircuit()
        for instruction in circuit:
            gate_data = stim.gate_data(instruction.name)
            if isinstance(instruction, stim.CircuitRepeatBlock):
                result.layers.append(
                    LoopLayer(
                        body=LayerCircuit.from_stim_circuit(instruction.body_copy()),
                        repetitions=instruction.repeat_count,
                    )
                )

            elif instruction.name == "R":
                result._feed_reset("Z", instruction.targets_copy())
            elif instruction.name == "RX":
                result._feed_reset("X", instruction.targets_copy())
            elif instruction.name == "RY":
                result._feed_reset("Y", instruction.targets_copy())

            elif instruction.name == "M":
                result._feed_m("Z", instruction.targets_copy())
            elif instruction.name == "MX":
                result._feed_m("X", instruction.targets_copy())
            elif instruction.name == "MY":
                result._feed_m("Y", instruction.targets_copy())

            elif instruction.name == "MR":
                result._feed_m("Z", instruction.targets_copy())
                result._feed_reset("Z", instruction.targets_copy())
            elif instruction.name == "MRX":
                result._feed_m("X", instruction.targets_copy())
                result._feed_reset("X", instruction.targets_copy())
            elif instruction.name == "MRY":
                result._feed_m("Y", instruction.targets_copy())
                result._feed_reset("Y", instruction.targets_copy())

            elif instruction.name == "XCX":
                result._feed_c("X", "X", instruction.targets_copy())
            elif instruction.name == "XCY":
                result._feed_c("X", "Y", instruction.targets_copy())
            elif instruction.name == "XCZ":
                result._feed_c("X", "Z", instruction.targets_copy())
            elif instruction.name == "YCX":
                result._feed_c("Y", "X", instruction.targets_copy())
            elif instruction.name == "YCY":
                result._feed_c("Y", "Y", instruction.targets_copy())
            elif instruction.name == "YCZ":
                result._feed_c("Y", "Z", instruction.targets_copy())
            elif instruction.name == "CX":
                result._feed_c("Z", "X", instruction.targets_copy())
            elif instruction.name == "CY":
                result._feed_c("Z", "Y", instruction.targets_copy())
            elif instruction.name == "CZ":
                result._feed_c("Z", "Z", instruction.targets_copy())

            elif gate_data.is_single_qubit_gate and gate_data.is_unitary:
                result._feed_named_rotation_instruction(instruction)

            elif instruction.name == "QUBIT_COORDS":
                result._feed_qubit_coords(
                    instruction.targets_copy(), instruction.gate_args_copy()
                )
            elif instruction.name == "SHIFT_COORDS":
                result._feed_shift_coords(instruction.gate_args_copy())
            elif instruction.name in ["DETECTOR", "OBSERVABLE_INCLUDE"]:
                result._feed(DetObsAnnotationLayer).circuit.append(instruction)

            elif instruction.name in ["ISWAP", "ISWAP_DAG"]:
                result._feed_iswap(instruction.targets_copy())
            elif instruction.name == "MPP":
                result._feed_mpp(instruction.targets_copy())
            elif instruction.name == "SWAP":
                result._feed_swap(instruction.targets_copy())
            elif instruction.name == "CXSWAP":
                result._feed_cxswap(instruction.targets_copy())
            elif instruction.name == "SWAPCX":
                result._feed_swapcx(instruction.targets_copy())

            elif instruction.name == "TICK":
                result.layers.append(EmptyLayer())

            elif instruction.name == "SQRT_XX" or instruction.name == "SQRT_XX_DAG":
                result._feed_sqrt_pp("X", instruction.targets_copy())
            elif instruction.name == "SQRT_YY" or instruction.name == "SQRT_YY_DAG":
                result._feed_sqrt_pp("Y", instruction.targets_copy())
            elif instruction.name == "SQRT_ZZ" or instruction.name == "SQRT_ZZ_DAG":
                result._feed_sqrt_pp("Z", instruction.targets_copy())
            elif (
                instruction.name == "DEPOLARIZE1"
                or instruction.name == "X_ERROR"
                or instruction.name == "Y_ERROR"
                or instruction.name == "Z_ERROR"
                or instruction.name == "DEPOLARIZE2"
                or instruction.name == "PAULI_CHANNEL_1"
            ):
                result._feed(NoiseLayer).circuit.append(instruction)

            else:
                raise NotImplementedError(f"{instruction=}")
        return result

    def __repr__(self) -> str:
        result = ["LayerCircuit(layers=["]
        for layer in self.layers:
            r = repr(layer)
            for line in r.split("\n"):
                result.append("\n    " + line)
            result.append(",")
        result.append("\n])")
        return "".join(result)

    def with_qubit_coords_at_start(self) -> "LayerCircuit":
        k = len(self.layers)
        merged_layer = QubitCoordAnnotationLayer()
        rev_layers = []
        while k > 0:
            k -= 1
            layer = self.layers[k]
            if isinstance(layer, QubitCoordAnnotationLayer):
                intersection = merged_layer.coords.keys() & layer.coords.keys()
                if intersection:
                    raise ValueError(
                        f"Qubit coords specified twice for qubits {sorted(intersection)}"
                    )
                merged_layer.coords.update(layer.coords)
            elif isinstance(layer, ShiftCoordAnnotationLayer):
                merged_layer.offset_by(layer.shift)
                rev_layers.append(layer)
            elif isinstance(layer, LoopLayer):
                if merged_layer.coords:
                    raise NotImplementedError("Moving qubit coords across a loop.")
                rev_layers.append(layer)
            else:
                rev_layers.append(layer)
        rev_layers.append(merged_layer)
        return LayerCircuit(layers=rev_layers[::-1])

    def with_locally_optimized_layers(self) -> "LayerCircuit":
        """Iterates over the circuit aggregating layer.optimized(second_layer)."""
        new_layers = []

        def do_layer(layer: Layer | None):
            if new_layers:
                new_layers[-1:] = new_layers[-1].locally_optimized(layer)
            else:
                new_layers.append(layer)
            while new_layers and (
                new_layers[-1] is None or new_layers[-1].is_vacuous()
            ):
                new_layers.pop()

        for e in self.layers:
            for opt in e.locally_optimized(None):
                do_layer(opt)
        do_layer(None)
        return LayerCircuit(layers=new_layers)

    def _resets_at_layer(self, k: int, *, end_resets: set[int]) -> set[int]:
        if k >= len(self.layers):
            return end_resets

        layer = self.layers[k]
        if isinstance(layer, ResetLayer):
            return layer.touched()
        if isinstance(layer, LoopLayer):
            return layer.body._resets_at_layer(0, end_resets=set())
        return set()

    def with_rotations_before_resets_removed(
        self, loop_boundary_resets: set[int] | None = None
    ) -> "LayerCircuit":
        all_touched = self.touched()
        if loop_boundary_resets is None:
            loop_boundary_resets = set()
        sets = [layer.touched() for layer in self.layers]
        sets.append(all_touched)
        resets = [
            self._resets_at_layer(k, end_resets=all_touched)
            for k in range(len(self.layers))
        ]
        if loop_boundary_resets is None:
            resets.append(all_touched)
        else:
            resets.append(
                loop_boundary_resets & (set() if len(resets) == 0 else resets[0])
            )
        new_layers = [layer.copy() for layer in self.layers]

        for k, layer in enumerate(new_layers):
            if isinstance(layer, LoopLayer):
                layer.body = layer.body.with_rotations_before_resets_removed(
                    loop_boundary_resets=self._resets_at_layer(
                        k + 1, end_resets=all_touched
                    )
                )
            elif isinstance(layer, RotationLayer):
                drops = []
                for q, gate in layer.named_rotations.items():
                    if gate != "I":
                        k2 = k + 1
                        while k2 < len(sets):
                            if q in sets[k2]:
                                if q in resets[k2]:
                                    drops.append(q)
                                break
                            k2 += 1
                for q in drops:
                    del layer.named_rotations[q]

        return LayerCircuit([layer for layer in new_layers if not layer.is_vacuous()])

    def with_clearable_rotation_layers_cleared(self) -> "LayerCircuit":
        """Removes rotation layers where every rotation in the layer can be moved to another layer.

        Each individual rotation can move through intermediate non-rotation layers as long as those
        layers don't touch the qubit being rotated.
        """
        sets = [layer.touched() for layer in self.layers]

        def scan(qubit: int, start_layer: int, delta: int) -> int | None:
            while True:
                start_layer += delta
                if start_layer < 0 or start_layer >= len(sets):
                    return None
                if (
                    isinstance(new_layers[start_layer], RotationLayer)
                    and not new_layers[start_layer].is_vacuous()
                ):
                    return start_layer
                if qubit in sets[start_layer]:
                    return None

        new_layers = [layer.copy() for layer in self.layers]
        cur_layer_index = 0
        while cur_layer_index < len(new_layers):
            layer = new_layers[cur_layer_index]
            if isinstance(layer, RotationLayer):
                rewrites = {}
                for q, r in layer.named_rotations.items():
                    if r == "I":
                        continue
                    new_layer_index = scan(q, cur_layer_index, -1)
                    if new_layer_index is None:
                        new_layer_index = scan(q, cur_layer_index, +1)
                    if new_layer_index is not None:
                        rewrites[q] = new_layer_index
                    else:
                        break
                else:
                    for q, r in layer.named_rotations.items():
                        if r == "I":
                            continue
                        new_layer_index = rewrites[q]
                        new_layer: RotationLayer = cast(
                            RotationLayer, new_layers[new_layer_index]
                        )
                        if new_layer_index > cur_layer_index:
                            new_layer.prepend_named_rotation(r, q)
                        else:
                            new_layer.append_named_rotation(r, q)
                        if new_layer.named_rotations.get(q) != "I":
                            sets[new_layer_index].add(q)
                        elif q in sets[new_layer_index]:
                            sets[new_layer_index].remove(q)
                    layer.named_rotations.clear()
                    sets[cur_layer_index].clear()
            elif isinstance(layer, LoopLayer):
                layer.body = layer.body.with_clearable_rotation_layers_cleared()
            cur_layer_index += 1
        return LayerCircuit([layer for layer in new_layers if not layer.is_vacuous()])

    def with_rotations_rolled_from_end_of_loop_to_start_of_loop(self) -> "LayerCircuit":
        """Rewrites loops so that they only have rotations at the start, not the end.

        This is useful for ensuring loops don't redundantly rotate at the loop boundary,
        by merging the rotations at the end with the rotations at the start or by
        making it clear rotations at the end were not needed because of the
        operations coming next.

        For example, this:

            REPEAT 5 {
                S 2 3 4
                R 0 1
                ...
                M 0 1
                H 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14
                DETECTOR rec[-1]
            }

        will become this:

            REPEAT 5 {
                H 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14
                S 2 3 4
                R 0 1
                ...
                M 0 1
                DETECTOR rec[-1]
            }

        which later optimization passes can then reduce further.
        """

        new_layers = []
        for layer in self.layers:
            handled = False
            if isinstance(layer, LoopLayer):
                loop_layers = list(layer.body.layers)
                rot_layer_index = len(loop_layers) - 1
                while rot_layer_index > 0:
                    if isinstance(
                        loop_layers[rot_layer_index],
                        (DetObsAnnotationLayer, ShiftCoordAnnotationLayer),
                    ):
                        rot_layer_index -= 1
                        continue
                    if isinstance(loop_layers[rot_layer_index], RotationLayer):
                        break
                    # Loop didn't end with a rotation layer; give up.
                    rot_layer_index = 0
                if rot_layer_index > 0:
                    handled = True
                    popped = cast(RotationLayer, loop_layers.pop(rot_layer_index))
                    loop_layers.insert(0, popped)

                    new_layers.append(popped.inverse())
                    new_layers.append(
                        LoopLayer(
                            body=LayerCircuit(loop_layers),
                            repetitions=layer.repetitions,
                        )
                    )
                    new_layers.append(popped.copy())
            if not handled:
                new_layers.append(layer)
        return LayerCircuit([layer for layer in new_layers if not layer.is_vacuous()])

    def with_rotations_merged_earlier(self) -> "LayerCircuit":
        sets = [layer.touched() for layer in self.layers]

        def scan(qubit: int, start_layer: int) -> int | None:
            while True:
                start_layer -= 1
                if start_layer < 0:
                    return None
                l = new_layers[start_layer]
                if isinstance(l, RotationLayer) and qubit in l.named_rotations:
                    return start_layer
                if qubit in sets[start_layer]:
                    return None

        new_layers = [layer.copy() for layer in self.layers]
        cur_layer_index = 0
        while cur_layer_index < len(new_layers):
            layer = new_layers[cur_layer_index]
            if isinstance(layer, RotationLayer):
                rewrites = {}
                for q, gate in layer.named_rotations.items():
                    if gate == "I":
                        continue
                    v = scan(q, cur_layer_index)
                    if v is not None:
                        rewrites[q] = v
                for q, dst in rewrites.items():
                    new_layer: RotationLayer = cast(RotationLayer, new_layers[dst])
                    new_layer.append_named_rotation(layer.named_rotations.pop(q), q)
                    sets[cur_layer_index].remove(q)
                    if new_layer.named_rotations.get(q):
                        sets[dst].add(q)
                    elif q in sets[dst]:
                        sets[dst].remove(q)
            elif isinstance(layer, LoopLayer):
                layer.body = layer.body.with_rotations_merged_earlier()
            cur_layer_index += 1
        return LayerCircuit([layer for layer in new_layers if not layer.is_vacuous()])

    def with_whole_rotation_layers_slid_earlier(self) -> "LayerCircuit":
        rev_layers = []
        cur_rot_layer: RotationLayer | None = None
        cur_rot_touched: set[int] | None = None
        for layer in self.layers[::-1]:
            if cur_rot_layer is not None and not layer.touched().isdisjoint(
                cur_rot_touched
            ):
                rev_layers.append(cur_rot_layer)
                cur_rot_layer = None
                cur_rot_touched = None
            if isinstance(layer, RotationLayer):
                layer = layer.copy()
                if cur_rot_layer is not None:
                    layer.named_rotations.update(cur_rot_layer.named_rotations)
                cur_rot_layer = layer
                cur_rot_touched = cur_rot_layer.touched()
            else:
                rev_layers.append(layer)
        if cur_rot_layer is not None:
            rev_layers.append(cur_rot_layer)
        return LayerCircuit(rev_layers[::-1])

    def with_ejected_loop_iterations(self) -> "LayerCircuit":
        new_layers = []
        for layer in self.layers:
            if isinstance(layer, LoopLayer):
                if layer.repetitions == 0:
                    pass
                elif layer.repetitions == 1:
                    new_layers.extend(layer.body.layers)
                elif layer.repetitions == 2:
                    new_layers.extend(layer.body.layers)
                    new_layers.extend(layer.body.layers)
                else:
                    new_layers.extend(layer.body.layers)
                    new_layers.append(
                        LoopLayer(
                            body=layer.body.copy(), repetitions=layer.repetitions - 2
                        )
                    )
                    new_layers.extend(layer.body.layers)
                    assert layer.repetitions > 2
            else:
                new_layers.append(layer)
        return LayerCircuit(new_layers)

    def without_empty_layers(self) -> "LayerCircuit":
        new_layers = []
        for layer in self.layers:
            if isinstance(layer, EmptyLayer):
                pass
            elif isinstance(layer, LoopLayer):
                new_layers.append(
                    LoopLayer(layer.body.without_empty_layers(), layer.repetitions)
                )
            else:
                new_layers.append(layer)
        return LayerCircuit(new_layers)

    def with_cleaned_up_loop_iterations(self) -> "LayerCircuit":
        new_layers = list(self.without_empty_layers().layers)
        k = 0
        while k < len(new_layers):
            if isinstance(new_layers[k], LoopLayer):
                body_layers = new_layers[k].body.layers
                reps = new_layers[k].repetitions
                while (
                    k >= len(body_layers)
                    and new_layers[k - len(body_layers) : k] == body_layers
                ):
                    new_layers[k - len(body_layers) : k] = []
                    k -= len(body_layers)
                    reps += 1
                while (
                    k + len(body_layers) < len(new_layers)
                    and new_layers[k + 1 : k + 1 + len(body_layers)] == body_layers
                ):
                    new_layers[k + 1 : k + 1 + len(body_layers)] = []
                    reps += 1
                new_layers[k] = LoopLayer(LayerCircuit(body_layers), reps)
            k += 1
        return LayerCircuit(new_layers)

    def with_whole_measurement_layers_slid_earlier(self) -> "LayerCircuit":
        rev_layers = []
        cur_meas_layer: MeasureLayer | None = None
        cur_meas_touched: set[int] | None = None
        for layer in self.layers[::-1]:
            if cur_meas_layer is not None and not layer.touched().isdisjoint(
                cur_meas_touched
            ):
                rev_layers.append(cur_meas_layer)
                cur_meas_layer = None
                cur_meas_touched = None

            if cur_meas_layer is not None and isinstance(
                layer, (FeedbackLayer, DetObsAnnotationLayer)
            ):
                layer = layer.with_rec_targets_shifted_by(-len(cur_meas_layer.targets))

            if isinstance(layer, MeasureLayer):
                layer = layer.copy()
                if cur_meas_layer is not None:
                    layer.bases.extend(cur_meas_layer.bases)
                    layer.targets.extend(cur_meas_layer.targets)
                cur_meas_layer = layer
                cur_meas_touched = cur_meas_layer.touched()
            else:
                rev_layers.append(layer)
        if cur_meas_layer is not None:
            rev_layers.append(cur_meas_layer)
        return LayerCircuit(rev_layers[::-1])

    def with_locally_merged_measure_layers(self) -> "LayerCircuit":
        new_layers = []
        k = 0
        while k < len(self.layers):
            if isinstance(self.layers[k], MeasureLayer):
                m1: MeasureLayer = self.layers[k]
                k2 = k + 1
                while k2 < len(self.layers) and isinstance(self.layers[k2], (DetObsAnnotationLayer, ShiftCoordAnnotationLayer)):
                    k2 += 1
                if k2 < len(self.layers) and isinstance(self.layers[k2], MeasureLayer):
                    m2: MeasureLayer = self.layers[k2]
                    if set(m1.targets).isdisjoint(set(m2.targets)):
                        new_layers.append(MeasureLayer(
                            targets=m1.targets + m2.targets,
                            bases=m1.bases + m2.bases,
                        ))
                        for k3 in range(k + 1, k2):
                            new_layers.append(self.layers[k3].with_rec_targets_shifted_by(-len(m2.targets)))
                        k = k2 + 1
                        continue
            new_layers.append(self.layers[k].copy())
            k += 1
        return LayerCircuit(new_layers)

    def with_whole_layers_slid_as_to_merge_with_previous_layer_of_same_type(
        self, layer_types: type | tuple[type, ...]
    ) -> "LayerCircuit":
        new_layers = list(self.layers)
        k = 0
        while k < len(new_layers):
            if isinstance(new_layers[k], layer_types):
                touched = new_layers[k].touched()
                k_prev = k
                while k_prev > 0 and new_layers[k_prev - 1].touched().isdisjoint(
                    touched
                ):
                    k_prev -= 1
                    if k_prev != k and type(new_layers[k_prev]) == type(new_layers[k]):
                        (new_layer,) = [
                            e
                            for e in new_layers[k_prev].locally_optimized(new_layers[k])
                            if e is not None
                        ]
                        del new_layers[k]
                        new_layers[k_prev] = new_layer
                        break
            k += 1
        return LayerCircuit(new_layers)

    def with_whole_layers_slid_as_early_as_possible_for_merge_with_same_layer(
        self, layer_types: type | tuple[type, ...]
    ) -> "LayerCircuit":
        new_layers = list(self.layers)
        k = 0
        while k < len(new_layers):
            if isinstance(new_layers[k], layer_types):
                touched = new_layers[k].touched()
                k_prev = k
                while k_prev > 0 and new_layers[k_prev - 1].touched().isdisjoint(
                    touched
                ):
                    k_prev -= 1
                while k_prev < k and type(new_layers[k_prev]) != type(new_layers[k]):
                    k_prev += 1
                if k_prev != k:
                    (new_layer,) = [
                        e
                        for e in new_layers[k_prev].locally_optimized(new_layers[k])
                        if e is not None
                    ]
                    del new_layers[k]
                    new_layers[k_prev] = new_layer
                    continue
            k += 1
        return LayerCircuit(new_layers)

    def with_irrelevant_tail_layers_removed(self) -> "LayerCircuit":
        irrelevant_layer_types_at_end = (
            ResetLayer,
            InteractLayer,
            FeedbackLayer,
            RotationLayer,
            SwapLayer,
            ISwapLayer,
            InteractSwapLayer,
            EmptyLayer,
        )
        result = list(self.layers)
        while len(result) > 0 and isinstance(result[-1], irrelevant_layer_types_at_end):
            result.pop()
        return LayerCircuit(result)

    def to_stim_circuit(self) -> stim.Circuit:
        circuit = stim.Circuit()
        tick_coming = False
        for layer in self.layers:
            if tick_coming and layer.requires_tick_before():
                circuit.append("TICK")
                tick_coming = False
            layer.append_into_stim_circuit(circuit)
            tick_coming |= layer.implies_eventual_tick_after()
        return circuit
