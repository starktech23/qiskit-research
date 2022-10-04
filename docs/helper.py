# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Helper functions for getting_started.ipynb"""

from typing import List

from qiskit.providers.backend import Backend
from qiskit.circuit import ClassicalRegister, Parameter, QuantumCircuit, QuantumRegister
from qiskit.circuit.library import HGate, IGate, SdgGate
from qiskit.opflow import I, X, Y, Z, EvolvedOp, PauliExpectation, PauliOp, Zero

from mapomatic import deflate_circuit
from qiskit_research.utils.convenience import attach_cr_pulses

POST_ROT_GATES = {
    "x": [HGate()],
    "y": [SdgGate(), HGate()],
    "z": [IGate()],
}

def ising_hamiltonian(
    num_spins: int, 
    JJ: Parameter, 
    hh: Parameter, 
    tt: Parameter,
    connectivity: str = 'nearest-neighbor',
) -> EvolvedOp:
    if connectivity == 'nearest-neighbor':
        int_terms = -JJ*sum([(I^idx) ^ Z ^ Z ^ (I ^ (num_spins - idx - 2)) for idx in range(num_spins-1)])
    elif connectivity == 'all-to-all':
        int_terms = -JJ * sum(
            [
                sum(
                    [
                        (I ^ idx) ^ Z ^ (I ^ jdx) ^ Z ^ (I ^ (num_spins - idx - jdx - 2))
                        for jdx in range(num_spins - idx - 1)
                    ]
                )
                for idx in range(num_spins - 1)
            ])
    ham = int_terms +  hh * sum([(I ^ idx) ^ X ^ (I ^ (num_spins - idx - 1)) for idx in range(num_spins)])
    return (ham * tt).exp_i()

def init_ground_state(num_spins: int) -> PauliOp:
    return Zero^num_spins

def get_magnetic_exps(U_ham: EvolvedOp) -> List[PauliOp]:
    num_spins = U_ham.num_qubits
    init_state = init_ground_state(num_spins)
    obsvs = [X^num_spins, Y^num_spins, Z^num_spins]
    return [(U_ham @ init_state).adjoint() @ obsv @ U_ham @ init_state for obsv in obsvs]

def build_ising_circuits(
    circ: QuantumCircuit,
    backend: Backend,
    num_trotter_steps: int,
    my_layout: List[int],
    param_bind: dict,
    time_range: List[float],
) -> List[QuantumCircuit]:
    # quantum register has weird number to accommadate appending
    qr = QuantumRegister(max(my_layout) + 1, "q")
    cr = ClassicalRegister(len(my_layout), "c")

    # Find the time parameter in the circuit
    for param in circ.parameters:
        if param.name == "t":
            tt = param

    circs = []
    for t_set in time_range:
        param_bind[tt] = t_set
        for meas_basis in ["x", "y", "z"]:
            total_circ = QuantumCircuit(qr, cr)
            for _ in range(num_trotter_steps):
                total_circ.append(circ.to_instruction(), qr)
            total_circ = total_circ.decompose()

            for gate in POST_ROT_GATES[meas_basis]:
                total_circ.append(gate, [my_layout])
            
            total_circ.measure(my_layout, cr)
            circs.append(attach_cr_pulses(total_circ, backend, param_bind))

    return circs

def exact_magnetization(
    U_ham: EvolvedOp, 
    param_bind: dict, 
    time_range: list[int]
):
    exps = get_magnetic_exps(U_ham)
    num_spins = U_ham.num_qubits
    mags = []
    for time in time_range:
        mag = []
        for exp in exps:
            param_bind[tt] = time
            mag.append(PauliExpectation().convert(exp.bind_parameters(param_bind)).eval() / num_spins)
        
        mags.append(mag)

    return mags