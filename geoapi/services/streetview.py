from geoapi.services.notifications import NotificationsService
from typing import List, Dict
from datetime import datetime

from geoapi.models import User, Streetview, StreetviewInstance, StreetviewSequence, StreetviewOrganization
from geoapi.db import db_session
from geoapi.log import logging

logger = logging.getLogger(__name__)


class StreetviewService:
    @staticmethod
    def list(user: User) -> List[Streetview]:
        """
        Get all streetview objects for a user
        :param user: User
        """
        streetviews = db_session.query(Streetview) \
            .join(User.streetviews) \
            .filter(User.username == user.username) \
            .filter(User.tenant_id == user.tenant_id) \
            .all()

        return streetviews


    @staticmethod
    def update(id: int, data: Dict) -> Streetview:
        """
        Update a Streetview object for a user.
        :param user: User
        :param service: str
        :return: Streetview
        """
        sv = StreetviewService.get(id)

        for key, value in data.items():
            setattr(sv, key, value)

        db_session.commit()

        return sv


    @staticmethod
    def create(user: User, data: Dict) -> Streetview:
        """
        Create a Streetview object for a user to contain service information.
        :param user: User
        :param service: str
        :return: Streetview
        """
        # TODO: Find better way to handle this
        svs = StreetviewService.list(user)
        if any(sv.service == data['service'] for sv in svs):
            return StreetviewService.updateByService(user, data['service'], data)

        sv = Streetview()
        sv.user_id = user.id

        for key, value in data.items():
            setattr(sv, key, value)

        db_session.add(sv)
        db_session.commit()

        return sv

    # TODO: Replace for instance
    @staticmethod
    def get(streetview_id: int) -> Streetview:
        """
        Retreive a single Streetview
        :param streetviewId: int
        :return: Streetview
        """
        return db_session.query(Streetview).get(streetview_id)

    @staticmethod
    def getByService(user: User, service: str):
        return db_session.query(Streetview)\
            .filter(Streetview.user_id == user.id)\
            .filter(Streetview.service == service)\
            .first()

    @staticmethod
    def updateByService(user: User, service: str, data: Dict) -> Streetview:
        sv = StreetviewService.getByService(user, service)

        for key, value in data.items():
            setattr(sv, key, value)

        db_session.commit()
        return sv

    @staticmethod
    def deleteByService(user: User, service: str):
        sv = StreetviewService.getByService(user, service)
        db_session.delete(sv)
        db_session.commit()

    @staticmethod
    def delete(id: int) -> None:
        """
        Delete a Streetview object.
        :param id: int
        :return: None
        """
        sv = StreetviewService.get(id)
        db_session.delete(sv)
        db_session.commit()

    @staticmethod
    def getOrganization(id: int) -> StreetviewOrganization:
        """
        Create a Streetview Instance object to link to tapis path and service.
        :param streetview: Streetview
        :param system_id: str
        :param path: str
        :return: None
        """
        return db_session.query(StreetviewOrganization).get(id)

    @staticmethod
    def getAllOrganizations(streetview_id: int) -> List[StreetviewOrganization]:
        """
        Get all the Streetview Organization objects for a service.
        :param streetview_id: int
        :return: List[StreetviewOrganization]
        """
        sv = StreetviewService.get(streetview_id)
        # service = db_session.query(Streetview).get(streetview.id)
        return sv.organizations
        # return Streetview.instances

    @staticmethod
    def createOrganization(streetview_id: int, data: Dict) -> StreetviewOrganization:
        """
        Create a Streetview Instance object to link to tapis path and service.
        :param streetview: Streetview
        :param key: str
        :param name: str
        :return: None
        """
        sv = StreetviewService.get(streetview_id)
        svo = StreetviewOrganization()
        svo.streetview_id = sv.id
        svo.key = data.get('key')
        svo.name = data.get('name')
        db_session.add(svo)
        db_session.commit()

        return svo

    @staticmethod
    def updateOrganization(id: int, data: Dict) -> StreetviewOrganization:
        """
        Update a Streetview Instance object to link to tapis path and service.
        :param streetview: Streetview
        :param system_id: str
        :param path: str
        :return: None
        """
        svo = StreetviewService.getOrganization(id)

        for key, value in data.items():
            setattr(svo, key, value)

        db_session.commit()

        return svo

    @staticmethod
    def deleteOrganization(id: int):
        """
        Delete a Streetview Instance object to link to tapis path and service.
        :param id: int
        :return: None
        """
        svo = StreetviewService.getOrganization(id)
        db_session.delete(svo)
        db_session.commit()

    @staticmethod
    def createInstance(streetview_id: int, system_id: str, path: str) -> StreetviewInstance:
        """
        Create a Streetview Instance object to link to tapis path and service.
        :param streetview: Streetview
        :param system_id: str
        :param path: str
        :return: None
        """
        svi = StreetviewInstance()
        svi.streetview_id = streetview_id
        svi.path = path
        svi.system_id = system_id
        db_session.add(svi)
        db_session.commit()

        return svi

    @staticmethod
    def getInstanceFromSystemPath(streetview_id: int, system_id: str, path: str) -> StreetviewInstance:
        """
        Get all the Streetview instance objects for a system and path.
        :param streetview_id: int
        :param system_id: str
        :param path: str
        :return: List[StreetviewInstance]
        """
        return db_session.query(StreetviewInstance)\
                         .filter(StreetviewInstance.streetview_id == streetview_id)\
                         .filter(StreetviewInstance.system_id == system_id)\
                         .filter(StreetviewInstance.path == path)\
                         .first()

    @staticmethod
    def deleteInstance(id: int) -> None:
        """
        Delete a Streetview Instance object.
        :param id: int
        :return: None
        """
        sv = db_session.query(StreetviewInstance).get(id)
        db_session.delete(sv)
        db_session.commit()

    @staticmethod
    def addSequenceToInstance(user: User, data: Dict) -> None:
        """
        Add Streetview Sequences with keys to an existing Streetview object with the given system and path.
        :param user: User
        :param data: Dict
        :return: None
        """
        dir = data['dir']
        svi = StreetviewService.getInstanceFromSystemPath(data['streetviewId'], dir['system'], dir['path'])

        if not svi:
            svi = StreetviewService.createInstance(data['streetviewId'], dir['system'], dir['path'])

        sequence = StreetviewService.createSequence(streetview_instance=svi, sequence_id=data['sequenceId'])
        svi.sequences.append(sequence)
        db_session.commit()

    # def createSequence(streetview_instance_id: int,
    @staticmethod
    def createSequence(streetview_instance: StreetviewInstance,
                       start_date: datetime=None,
                       end_date: datetime=None,
                       bbox: str=None,
                       sequence_id: str=None) -> StreetviewSequence:
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
        if sequence_id:
            seq.sequence_id = sequence_id
        db_session.add(seq)
        db_session.commit()
        return seq

    @staticmethod
    def getSequence(id: int) -> StreetviewSequence:
        """
        Get a Streetview Sequence by its id.
        :param id: int
        :return: StreetviewSequence
        """
        sequence = db_session.query(StreetviewSequence).get(id)
        return sequence

    @staticmethod
    def deleteSequence(id: int) -> None:
        """
        Delete a Streetview Sequence by its id.
        :param id: int
        :return: None
        """
        seq = db_session.query(StreetviewSequence).get(id)
        db_session.delete(seq)
        db_session.commit()

    @staticmethod
    def updateSequence(id: int, data: Dict) -> StreetviewSequence:
        """
        Update a Streetview Sequence.
        :param sequence_id: int
        :param data: Dict
        :return: StreetviewSequence
        """
        sequence = StreetviewService.getSequence(id)

        for key, value in data.items():
            setattr(sequence, key, value)
        db_session.commit()

        return sequence
