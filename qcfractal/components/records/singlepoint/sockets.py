from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from qcelemental.models import AtomicInput as QCEl_AtomicInput, AtomicResult as QCEl_AtomicResult
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import contains_eager

from qcfractal.components.records.sockets import BaseRecordSocket
from qcfractal.components.wavefunctions.db_models import WavefunctionStoreORM
from qcfractal.db_socket.helpers import insert_general
from qcportal.metadata_models import InsertMetadata, QueryMetadata
from qcportal.molecules import Molecule
from qcportal.records import PriorityEnum, RecordStatusEnum
from qcportal.records.singlepoint import (
    QCSpecification,
    WavefunctionProperties,
    SinglepointQueryBody,
)
from .db_models import QCSpecificationORM, SinglepointRecordORM

if TYPE_CHECKING:
    from sqlalchemy.orm.session import Session
    from qcfractal.db_socket.socket import SQLAlchemySocket
    from typing import List, Dict, Tuple, Optional, Sequence, Any, Union


def wavefunction_to_orm(wavefunction: Optional[WavefunctionProperties]) -> Optional[WavefunctionStoreORM]:
    """
    Convert a QCElemental wavefunction into a wavefunction ORM
    """

    _wfn_all_fields = set(WavefunctionProperties.__fields__.keys())
    logger = logging.getLogger(__name__)

    if wavefunction is None:
        return None

    wfn_dict = wavefunction.dict()
    available_keys = set(wfn_dict.keys())

    # Extra fields are trimmed as we have a column *per* wavefunction structure.
    extra_fields = available_keys - _wfn_all_fields
    if extra_fields:
        logger.warning(f"Too much wavefunction data for result, removing extra data: {extra_fields}")
        available_keys &= _wfn_all_fields

    wavefunction_save = {k: wfn_dict[k] for k in available_keys}
    wfn_prop = WavefunctionProperties(**wavefunction_save)
    return WavefunctionStoreORM.from_model(wfn_prop)


class SinglepointRecordSocket(BaseRecordSocket):
    """
    Socket for handling singlepoint computations
    """

    # Used by the base class
    record_orm = SinglepointRecordORM
    specification_orm = QCSpecificationORM

    def __init__(self, root_socket: SQLAlchemySocket):
        BaseRecordSocket.__init__(self, root_socket)
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def get_children_select() -> List[Any]:
        return []

    def generate_task_specification(self, record_orm: SinglepointRecordORM) -> Dict[str, Any]:

        specification = record_orm.specification
        molecule = record_orm.molecule.model_dict()

        model = {"method": specification.method}
        if specification.basis:
            model["basis"] = specification.basis

        qcschema_input = QCEl_AtomicInput(
            driver=specification.driver,
            model=model,
            molecule=molecule,
            keywords=specification.keywords.values,
            protocols=specification.protocols,
        )

        return {
            "function": "qcengine.compute",
            "args": [qcschema_input.dict(), specification.program],
            "kwargs": {},
        }

    def update_completed_task(
        self, session: Session, record_orm: SinglepointRecordORM, result: QCEl_AtomicResult, manager_name: str
    ) -> None:
        # Update the fields themselves
        record_orm.return_result = result.return_result
        record_orm.properties = result.properties.dict(encoding="json")
        record_orm.wavefunction = wavefunction_to_orm(result.wavefunction)
        record_orm.extras = result.extras

    def insert_complete_record(
        self,
        session: Session,
        result: QCEl_AtomicResult,
    ) -> SinglepointRecordORM:

        qc_spec = QCSpecification(
            program=result.provenance.creator.lower(),
            driver=result.driver,
            method=result.model.method,
            basis=result.model.basis,
            keywords=result.keywords,
            protocols=result.protocols,
        )

        spec_meta, spec_id = self.add_specification(qc_spec, session=session)
        if not spec_meta.success:
            raise RuntimeError(
                "Aborted single point insertion - could not add specification: " + spec_meta.error_string
            )

        mol_meta, mol_ids = self.root_socket.molecules.add([result.molecule], session=session)
        if not mol_meta.success:
            raise RuntimeError("Aborted single point insertion - could not add molecule: " + spec_meta.error_string)

        record_orm = SinglepointRecordORM()
        record_orm.is_service = False
        record_orm.specification_id = spec_id
        record_orm.molecule_id = mol_ids[0]
        record_orm.status = RecordStatusEnum.complete
        record_orm.return_result = result.return_result
        record_orm.properties = result.properties.dict(encoding="json")
        record_orm.wavefunction = wavefunction_to_orm(result.wavefunction)
        record_orm.extras = result.extras

        session.add(record_orm)
        session.flush()
        return record_orm

    def add_specification(
        self, qc_spec: QCSpecification, *, session: Optional[Session] = None
    ) -> Tuple[InsertMetadata, Optional[int]]:
        """
        Adds a specification for a singlepoint calculation to the database, returning its id.

        If an identical specification exists, then no insertion takes place and the id of the existing
        specification is returned.

        Parameters
        ----------
        qc_spec
            Specification to add to the database
        session
            An existing SQLAlchemy session to use. If None, one will be created. If an existing session
            is used, it will be flushed (but not committed) before returning from this function.

        Returns
        -------
        :
            Metadata about the insertion, and the id of the specification.
        """

        protocols_dict = qc_spec.protocols.dict(exclude_defaults=True)

        # TODO - if error_correction is manually specified as the default, then it will be an empty dict
        if "error_correction" in protocols_dict:
            erc = protocols_dict["error_correction"]
            pol = erc.get("policies", dict())
            if len(pol) == 0:
                erc.pop("policies", None)
            if len(erc) == 0:
                protocols_dict.pop("error_correction")

        basis = "" if qc_spec.basis is None else qc_spec.basis

        with self.root_socket.optional_session(session, False) as session:
            # Add the keywords
            meta, kw_ids = self.root_socket.keywords.add([qc_spec.keywords], session=session)
            if not meta.success:
                return (
                    InsertMetadata(
                        error_description="Unable to add keywords: " + meta.error_string,
                    ),
                    None,
                )

            stmt = (
                insert(QCSpecificationORM)
                .values(
                    program=qc_spec.program,
                    driver=qc_spec.driver,
                    method=qc_spec.method,
                    basis=basis,
                    keywords_id=kw_ids[0],
                    protocols=protocols_dict,
                )
                .on_conflict_do_nothing()
                .returning(QCSpecificationORM.id)
            )

            r = session.execute(stmt).scalar_one_or_none()
            if r is not None:
                return InsertMetadata(inserted_idx=[0]), r
            else:
                # Specification was already existing
                stmt = select(QCSpecificationORM.id).filter_by(
                    program=qc_spec.program,
                    driver=qc_spec.driver,
                    method=qc_spec.method,
                    basis=basis,
                    keywords_id=kw_ids[0],
                    protocols=protocols_dict,
                )

                r = session.execute(stmt).scalar_one()
                return InsertMetadata(existing_idx=[0]), r

    def query(
        self,
        query_data: SinglepointQueryBody,
        *,
        session: Optional[Session] = None,
    ) -> Tuple[QueryMetadata, List[Dict[str, Any]]]:
        """
        Query singlepoint records

        Parameters
        ----------
        query_data
            Fields/filters to query for
        session
            An existing SQLAlchemy session to use. If None, one will be created. If an existing session
            is used, it will be flushed (but not committed) before returning from this function.

        Returns
        -------
        :
            Metadata about the results of the query, and a list of records (as dictionaries)
            that were found in the database.
        """

        and_query = []
        need_join = False

        if query_data.program is not None:
            and_query.append(QCSpecificationORM.program.in_(query_data.program))
            need_join = True
        if query_data.driver is not None:
            and_query.append(QCSpecificationORM.driver.in_(query_data.driver))
            need_join = True
        if query_data.method is not None:
            and_query.append(QCSpecificationORM.method.in_(query_data.method))
            need_join = True
        if query_data.basis is not None:
            and_query.append(QCSpecificationORM.basis.in_(query_data.basis))
            need_join = True
        if query_data.molecule_id is not None:
            and_query.append(SinglepointRecordORM.molecule_id.in_(query_data.molecule_id))

        stmt = select(SinglepointRecordORM)

        if need_join:
            stmt = stmt.join(SinglepointRecordORM.specification).options(
                contains_eager(SinglepointRecordORM.specification)
            )

        stmt = stmt.where(*and_query)

        return self.root_socket.records.query_base(
            stmt=stmt,
            orm_type=SinglepointRecordORM,
            query_data=query_data,
            session=session,
        )

    def add_internal(
        self,
        molecule_ids: Sequence[int],
        qc_spec_id: int,
        tag: str,
        priority: PriorityEnum,
        *,
        session: Optional[Session] = None,
    ) -> Tuple[InsertMetadata, List[Optional[int]]]:
        """
        Internal function for adding new singlepoint computations

        This function expects that the molecules and specification are already added to the
        database and that the ids are known.

        This checks if the calculations already exist in the database. If so, it returns
        the existing id, otherwise it will insert it and return the new id.

        Parameters
        ----------
        molecule_ids
            IDs of the molecules to run the computation with. One record will be added per molecule.
        qc_spec_id
            ID of the specification
        tag
            The tag for the task. This will assist in routing to appropriate compute managers.
        priority
            The priority for the computation
        session
            An existing SQLAlchemy session to use. If None, one will be created. If an existing session
            is used, it will be flushed (but not committed) before returning from this function.

        Returns
        -------
        :
            Metadata about the insertion, and a list of record ids. The ids will be in the
            order of the input molecules
        """

        tag = tag.lower()

        with self.root_socket.optional_session(session, False) as session:

            # Get the spec orm. The full orm will be needed for create_task
            stmt = select(QCSpecificationORM).where(QCSpecificationORM.id == qc_spec_id)
            spec_orm = session.execute(stmt).scalar_one()

            all_orm = []

            for mid in molecule_ids:
                sp_orm = SinglepointRecordORM(
                    is_service=False,
                    specification=spec_orm,
                    specification_id=qc_spec_id,
                    molecule_id=mid,
                    status=RecordStatusEnum.waiting,
                )

                self.create_task(sp_orm, tag, priority)
                all_orm.append(sp_orm)

            meta, ids = insert_general(
                session,
                all_orm,
                (SinglepointRecordORM.specification_id, SinglepointRecordORM.molecule_id),
                (SinglepointRecordORM.id,),
            )
            return meta, [x[0] for x in ids]

    def add(
        self,
        molecules: Sequence[Union[int, Molecule]],
        qc_spec: QCSpecification,
        tag: str,
        priority: PriorityEnum,
        *,
        session: Optional[Session] = None,
    ) -> Tuple[InsertMetadata, List[Optional[int]]]:
        """
        Adds new singlepoint calculations

        This checks if the calculations already exist in the database. If so, it returns
        the existing id, otherwise it will insert it and return the new id.

        Parameters
        ----------
        molecules
            Molecules to compute using the specification
        qc_spec
            Specification for the calculations
        tag
            The tag for the task. This will assist in routing to appropriate compute managers.
        priority
            The priority for the computation
        session
            An existing SQLAlchemy session to use. If None, one will be created. If an existing session
            is used, it will be flushed (but not committed) before returning from this function.

        Returns
        -------
        :
            Metadata about the insertion, and a list of record ids. The ids will be in the
            order of the input molecules
        """

        with self.root_socket.optional_session(session, False) as session:

            # First, add the specification
            spec_meta, spec_id = self.add_specification(qc_spec, session=session)
            if not spec_meta.success:
                return (
                    InsertMetadata(
                        error_description="Aborted - could not add specification: " + spec_meta.error_string
                    ),
                    [],
                )

            # Now the molecules
            mol_meta, mol_ids = self.root_socket.molecules.add_mixed(molecules, session=session)
            if not mol_meta.success:
                return (
                    InsertMetadata(error_description="Aborted - could not add all molecules: " + mol_meta.error_string),
                    [],
                )

            return self.add_internal(mol_ids, spec_id, tag, priority, session=session)
