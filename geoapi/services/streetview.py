from typing import List, Dict
from datetime import datetime

from geoapi.models import (
    User,
    Streetview,
    StreetviewInstance,
    StreetviewSequence,
    StreetviewOrganization,
    Project,
)
from geoapi.log import logging


logger = logging.getLogger(__name__)


class StreetviewService:
    @staticmethod
    def nullify_expired_tokens(
        database_session, streetviews: List[Streetview]
    ) -> List[Streetview]:
        """
        Check a list of streetview objects for expired tokens and nullify them
        Commits changes to the database if any tokens were nullified
        """
        changes_made = False
        for streetview in streetviews:
            if streetview.token_expires_at is None and streetview.token is not None:
                logger.info(
                    f"Token missing token_expires_at so for streetview service {streetview.service}, so nullifying token info"
                )
                streetview.token = None
                streetview.token_expires_at = None
                changes_made = True
            else:
                now_with_tz = datetime.now().astimezone(
                    streetview.token_expires_at.tzinfo
                )
                if streetview.token_expires_at < now_with_tz:
                    logger.info(
                        f"Token expired for streetview service {streetview.service}, nullifying token info"
                    )

                    streetview.token = None
                    streetview.token_expires_at = None
                    changes_made = True
        if changes_made:
            database_session.commit()
            for streetview in streetviews:
                database_session.refresh(streetview)

        return streetviews

    @staticmethod
    def list(database_session, user: User) -> List[Streetview]:
        """
        Get all streetview objects for a user
        :param user: User
        :return: List[Streetview]
        """
        streetviews = (
            database_session.query(Streetview)
            .join(User.streetviews)
            .filter(User.username == user.username)
            .filter(User.tenant_id == user.tenant_id)
            .all()
        )

        return StreetviewService.nullify_expired_tokens(database_session, streetviews)

    @staticmethod
    def create(database_session, user: User, data: Dict) -> Streetview:
        """
        Create a Streetview object for a user to contain service information.
        :param user: User
        :param data: Dict
        :return: Streetview
        """
        if StreetviewService.getByService(database_session, user, data["service"]):
            StreetviewService.deleteByService(database_session, user, data["service"])

        sv = Streetview()
        sv.user_id = user.id

        for key, value in data.items():
            setattr(sv, key, value)

        database_session.add(sv)
        database_session.commit()

        return sv

    @staticmethod
    def get(database_session, streetview_id: int) -> Streetview:
        """
        Retrieve a single Streetview Service
        :param streetview_id: int
        :return: Streetview
        """
        streetview = database_session.get(Streetview, streetview_id)
        if streetview:
            StreetviewService.nullify_expired_tokens(database_session, [streetview])
        return streetview

    @staticmethod
    def getByService(database_session, user: User, service: str) -> Streetview:
        """
        Retrieve a single Streetview Service by service name
        :param user: User
        :param service: str
        :return: Streetview
        """
        streetview = (
            database_session.query(Streetview)
            .filter(Streetview.user_id == user.id)
            .filter(Streetview.service == service)
            .first()
        )

        # Check for expired token and nullify if needed
        if streetview:
            StreetviewService.nullify_expired_tokens(database_session, [streetview])
        return streetview

    @staticmethod
    def updateByService(
        database_session, user: User, service: str, data: Dict
    ) -> Streetview:
        """
        Update a single Streetview Service by service name
        :param user: User
        :param service: str
        :param data: Dict
        :return: Streetview
        """
        sv = StreetviewService.getByService(database_session, user, service)

        for key, value in data.items():
            setattr(sv, key, value)

        database_session.commit()
        return sv

    @staticmethod
    def deleteByService(database_session, user: User, service: str):
        """
        Delete a single Streetview Service by service name
        :param user: User
        :param service: str
        :return: None
        """
        sv = StreetviewService.getByService(database_session, user, service)
        database_session.delete(sv)
        database_session.commit()

    @staticmethod
    def deleteAuthByService(database_session, user: User, service: str):
        """
        Removes auth for a single Streetview Service by service name
        :param user: User
        :param service: str
        :return: None
        """
        sv = StreetviewService.getByService(database_session, user, service)
        if sv:
            sv.token = None
            sv.token_expires_at = None
            database_session.commit()

    @staticmethod
    def delete(database_session, id: int) -> None:
        """
        Delete a Streetview object.
        :param id: int
        :return: None
        """
        sv = StreetviewService.get(database_session, id)
        database_session.delete(sv)
        database_session.commit()

    @staticmethod
    def getOrganization(database_session, id: int) -> StreetviewOrganization:
        """
        Get a Streetview Organization object
        :param id: int
        :return: StreetviewOrganization
        """
        return database_session.get(StreetviewOrganization, id)

    @staticmethod
    def getAllOrganizations(
        database_session, user: User, service: str
    ) -> List[StreetviewOrganization]:
        """
        Get all the Streetview Organization objects for a service.
        :param user: User
        :param service: str
        :return: List[StreetviewOrganization]
        """
        sv = StreetviewService.getByService(database_session, user, service)
        return sv.organizations

    @staticmethod
    def createOrganization(
        database_session, user: User, service: str, data: Dict
    ) -> StreetviewOrganization:
        """
        Create a Streetview Organization object
        :param service: str
        :param data: Dict
        :return: StreetviewOrganization
        """
        sv = StreetviewService.getByService(database_session, user, service)
        svo = StreetviewOrganization()
        svo.streetview_id = sv.id
        svo.key = data.get("key")
        svo.name = data.get("name")
        svo.slug = data.get("slug")
        database_session.add(svo)
        database_session.commit()

        return svo

    @staticmethod
    def updateOrganization(
        database_session, id: int, data: Dict
    ) -> StreetviewOrganization:
        """
        Update a Streetview Organization object
        :param id: int
        :param data: Dict
        :return: StreetviewOrganization
        """
        svo = StreetviewService.getOrganization(database_session, id)

        for key, value in data.items():
            setattr(svo, key, value)

        database_session.commit()

        return svo

    @staticmethod
    def deleteOrganization(database_session, id: int):
        """
        Delete a Streetview Organization object
        :param id: int
        :return: None
        """
        svo = StreetviewService.getOrganization(database_session, id)
        database_session.delete(svo)
        database_session.commit()

    @staticmethod
    def createInstance(
        database_session, streetview_id: int, system_id: str, path: str
    ) -> StreetviewInstance:
        """
        Create a Streetview Instance object.
        :param streetview_id: int
        :param system_id: str
        :param path: str
        :return: StreetviewInstance
        """
        svi = StreetviewInstance()
        svi.streetview_id = streetview_id
        svi.path = path
        svi.system_id = system_id
        database_session.add(svi)
        database_session.commit()

        return svi

    @staticmethod
    def getInstances(database_session, projectId: int) -> List[StreetviewInstance]:
        project = database_session.get(Project, projectId)
        return project.streetview_instances

    @staticmethod
    def addInstanceToProject(
        database_session, projectId: int, streetview_instance_id: int
    ) -> None:
        project = database_session.get(Project, projectId)
        streetview_instance = database_session.get(
            StreetviewInstance, streetview_instance_id
        )
        project.streetview_instances.append(streetview_instance)
        database_session.commit()

    @staticmethod
    def sequenceFromFeature(database_session, featureId: int):
        return (
            database_session.query(StreetviewSequence)
            .filter(StreetviewSequence.feature.id == featureId)
            .first()
        )

    @staticmethod
    def getInstanceFromSystemPath(
        database_session, streetview_id: int, system_id: str, path: str
    ) -> StreetviewInstance:
        """
        Get a Streetview instance object for a system and path.
        :param streetview_id: int
        :param system_id: str
        :param path: str
        :return: StreetviewInstance
        """
        return (
            database_session.query(StreetviewInstance)
            .filter(StreetviewInstance.streetview_id == streetview_id)
            .filter(StreetviewInstance.system_id == system_id)
            .filter(StreetviewInstance.path == path)
            .first()
        )

    @staticmethod
    def deleteInstance(database_session, id: int) -> None:
        """
        Delete a Streetview Instance object.
        :param id: int
        :return: None
        """
        sv = database_session.get(StreetviewInstance, id)
        database_session.delete(sv)
        database_session.commit()

    @staticmethod
    def addSequenceToInstance(database_session, user: User, data: Dict) -> None:
        """
        Add Streetview Sequences with keys to an existing Streetview object.
        :param user: User
        :param data: Dict
        :return: None
        """
        dir = data["dir"]
        svi = StreetviewService.getInstanceFromSystemPath(
            database_session, data["streetviewId"], dir["system"], dir["path"]
        )

        if not svi:
            svi = StreetviewService.createInstance(
                database_session, data["streetviewId"], dir["system"], dir["path"]
            )

        sequence = StreetviewService.createSequence(
            database_session,
            streetview_instance=svi,
            sequence_id=data["sequenceId"],
            organization_id=data["organizationId"],
        )
        svi.sequences.append(sequence)
        database_session.commit()

    @staticmethod
    def createSequence(
        database_session,
        streetview_instance: StreetviewInstance,
        start_date: datetime = None,
        end_date: datetime = None,
        bbox: str = None,
        organization_id: str = None,
        sequence_id: str = None,
    ) -> StreetviewSequence:
        """
        Create a Streetview Sequence to link to a Streetview Instance.
        :param streetview_instance_id: int
        :param start_date: datetime
        :param end_date: datetime
        :param bbox: bool
        :param sequence_id: str
        :return: StreetviewSequence
        """
        seq = StreetviewSequence()
        # seq.streetview_instance_id = streetview_instance_id
        seq.streetview_instance_id = streetview_instance.id
        if start_date:
            seq.start_date = start_date
        if end_date:
            seq.end_date = end_date
        if bbox:
            seq.bbox = bbox
        if organization_id:
            seq.organization_id = organization_id
        if sequence_id:
            seq.sequence_id = sequence_id
        database_session.add(seq)
        database_session.commit()
        return seq

    @staticmethod
    def getSequenceFromId(database_session, sequence_id: str) -> StreetviewSequence:
        """
        Get a Streetview Sequence by its sequence_id.
        :param sequence_id: str
        :return: StreetviewSequence
        """
        sequence = (
            database_session.query(StreetviewSequence)
            .filter(StreetviewSequence.sequence_id == sequence_id)
            .first()
        )
        return sequence

    @staticmethod
    def getSequence(database_session, id: int) -> StreetviewSequence:
        """
        Get a Streetview Sequence by its id.
        :param id: int
        :return: StreetviewSequence
        """
        sequence = database_session.get(StreetviewSequence, id)
        return sequence

    @staticmethod
    def deleteSequence(database_session, id: int) -> None:
        """
        Delete a Streetview Sequence by its id.
        :param id: int
        :return: None
        """
        seq = database_session.get(StreetviewSequence, id)
        database_session.delete(seq)
        database_session.commit()

    @staticmethod
    def updateSequence(database_session, id: int, data: Dict) -> StreetviewSequence:
        """
        Update a Streetview Sequence.
        :param sequence_id: int
        :param data: Dict
        :return: StreetviewSequence
        """
        sequence = StreetviewService.getSequence(database_session, id)

        for key, value in data.items():
            setattr(sequence, key, value)
        database_session.commit()

        return sequence
