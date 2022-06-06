from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# def test_optimization_dataset_general(storage_socket: SQLAlchemySocket, snowflake_client):
#    ds_id = storage_socket.datasets.optimization.add(
#        "Test Optimization Dataset",
#        description="A description",
#        tagline="A tagline",
#        group="test_group",
#    )
#
#    spec1 = OptimizationSpecification(
#        program="geometric",
#        keywords={},
#        qc_specification=QCSpecification(
#            program="psi4", method="b3lyp", basis="sto-3g", keywords={"values": {}}
#        ),
#    )
#
#    spec2 = OptimizationSpecification(
#        program="geometric",
#        keywords={},
#        qc_specification=QCSpecification(
#            program="psi4", method="hf", basis="sto-3g", keywords={"values": {"maxiter": 99}}
#        ),
#    )
#
#    storage_socket.datasets.optimization.add_specifications(
#        ds_id,
#        [
#            OptimizationDatasetSpecification(name="test_spec_1", specification=spec1, comment="a_comment"),
#            OptimizationDatasetSpecification(name="test_spec_2", specification=spec2, comment="a_comment_2"),
#        ],
#    )
#
#    new_entries = []
#    for m in ["neon_tetramer", "hooh", "water_dimer_minima", "peroxide2"]:
#        mol_data = load_molecule_data(m)
#        opt_ent = OptimizationDatasetNewEntry(
#            name=m, initial_molecule=mol_data, additional_keywords={}, attributes={"attr_name": m}
#        )
#        new_entries.append(opt_ent)
#
#    new_entries[1].additional_keywords = {"maxiter": 1000}
#
#    storage_socket.datasets.optimization.add_entries(ds_id, new_entries)
#
#    storage_socket.datasets.optimization.submit(ds_id)
#