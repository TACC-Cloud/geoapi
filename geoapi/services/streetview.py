from geoapi.services.notifications import NotificationsService
from typing import List, Dict
from datetime import datetime

from geoapi.models import User, Streetview, StreetviewSequence, Project
from geoapi.db import db_session
from geoapi.log import logging

logger = logging.getLogger(__name__)


class StreetviewService:
    @staticmethod
    def getToken(user: User, service: str) -> str:
        if service == 'google':
            return user.google_jwt
        else:
            return user.mapillary_jwt

    @staticmethod
    def setToken(user: User, service: str, token: str) -> None:
        if service == 'google':
            user.google_jwt = token
        else:
            user.mapillary_jwt = token
        db_session.commit()

    @staticmethod
    def deleteToken(user: User, service: str) -> None:
        if service == 'google':
            user.google_jwt = None
        else:
            user.mapillary_jwt = None
            db_session.commit()

    @staticmethod
    def get(streetviewId: int) -> Streetview:
        """
        Retreive a single Streetview
        :param streetviewId: int
        :return: Streetview
        """
        return db_session.query(Streetview).get(streetviewId)

    @staticmethod
    def create(user_id: int, system_id: str, path: str) -> Streetview:
        """
        Create a Streetview model to link to tapis path and service.
        :param user_id: int
        :param system_id: str
        :param path: str
        :return: None
        """
        sv = Streetview()
        sv.user_id = user_id
        sv.path = path
        sv.system_id = system_id
        db_session.add(sv)
        db_session.commit()

        return sv

    @staticmethod
    def delete(streetview_id: int) -> None:
        """
        Delete a Streetview object.
        :param streetview_id: int
        :return: None
        """
        sv = db_session.query(Streetview).get(streetview_id)
        db_session.delete(sv)
        db_session.commit()

    @staticmethod
    def getFromSystemPath(user: User, system_id: str, path: str) -> List[Streetview]:
        """
        Get all the Streetview object for a system and path.
        :param user: User
        :param system_id: str
        :param path: str
        :return: List[Streetview]
        """
        return db_session.query(Streetview)\
                         .filter(Streetview.system_id == system_id)\
                         .filter(Streetview.path == path)\
                         .all()

    @staticmethod
    def getAll(user: User) -> List[Streetview]:
        """
        Get all the Streetview object for a user.
        :param user: User
        :return: List[Streetview]
        """
        current_user = db_session.query(User).get(user.id)
        return current_user.streetviews


    @staticmethod
    def addToProject(streetview_id: int, project_id: int):
        streetview = db_session.query(Streetview).get(streetview_id)
        current_project = db_session.query(Project).get(project_id)

        current_project.streetviews.append(streetview)
        db_session.commit()


    @staticmethod
    def getProjectStreetviews(project_id: int) -> List[Streetview]:
        current_project = db_session.query(Project).get(project_id)
        return current_project.streetviews


    @staticmethod
    def deleteProjectStreetview(streetview_id: int, project_id: int):
        current_project = db_session.query(Project).get(project_id)
        removed_streetviews = filter(lambda sv: sv.id != streetview_id, current_project.streetviews)
        current_project.streetviews = removed_streetviews
        db_session.commit()


    @staticmethod
    def getSystemPaths(user: User) -> List[tuple]:
        """
        Get all the Streetview object paths for a user.
        :param user: User
        :return: List[tuple]
        """
        sv_list = StreetviewService.getAll(user)
        return list(map(lambda x: (x.system_id, x.path), sv_list))

    @staticmethod
    def addSequenceToStreetview(user: User, data: Dict) -> None:
        """
        Add Streetview Sequences with keys to an existing Streetview object with the given system and path.
        :param user: User
        :param data: Dict
        :param service: str
        :return: None
        """
        dir = data['dir']
        svp = StreetviewService.getFromSystemPath(user, dir['system'], dir['path'])

        if len(svp) == 0:
            svp = StreetviewService.create(user.id, dir['system'], dir['path'])
        else:
            svp = svp[0]

        for seq in data['sequences']:
            if seq in list(map(lambda x: x.sequence_key, svp.sequences)):
                NotificationsService.create(user, "warning", "Seqence already exists for that folder!")
                continue
            else:
                sequence = StreetviewService.createSequence(streetview_id=svp.id, sequence_key=seq, service=data['service'])
                svp.sequences.append(sequence)
                db_session.commit()

    @staticmethod
    def createSequence(streetview_id: int,
                       service: str = None,
                       sequence_key: str = None,
                       start_date: datetime = None,
                       end_date: datetime = None,
                       organization_key: str = None,
                       bbox: str = None) -> StreetviewSequence:
        """
        Create a Streetview Sequence to link to a streetview service sequence.
        :param streetview_id: int
        :param service: str
        :param sequence_key: str
        :param start_date: datetime
        :param end_date: datetime
        :param organization_key: str
        :param bbox: bool
        :return: StreetviewSequence
        """
        seq = StreetviewSequence()
        seq.streetview_id = streetview_id
        if service:
            seq.service = service
        if sequence_key:
            seq.sequence_key = sequence_key
        if start_date:
            seq.start_date = start_date
        if end_date:
            seq.end_date = end_date
        if organization_key:
            seq.organization_key = organization_key
        if bbox:
            seq.bbox = bbox
        db_session.add(seq)
        db_session.commit()
        return seq

    @staticmethod
    def getSequence(sequence_id: int) -> StreetviewSequence:
        """
        Get a Streetview Sequence by its sequence id.
        :param sequence_id: int
        :return: StreetviewSequence
        """
        sequence = db_session.query(StreetviewSequence).get(sequence_id)
        return sequence

    @staticmethod
    def deleteSequence(sequence_id: int) -> None:
        """
        Delete a Streetview Sequence by its sequence id.
        :param sequence_id: int
        :return: None
        """
        seq = db_session.query(StreetviewSequence).get(sequence_id)
        db_session.delete(seq)
        db_session.commit()

    @staticmethod
    def deleteBySequenceKey(sequence_key: str, streetview_id: int) -> None:
        """
        Delete a Streetview Sequence by its sequence key and streetview id.
        :param sequence_key: str
        :param streetview_id: int
        :return: None
        """
        seqs = db_session.query(StreetviewSequence) \
                         .filter(StreetviewSequence.sequence_key == sequence_key) \
                         .filter(StreetviewSequence.streetview_id == streetview_id) \
                         .all()

        for seq in seqs:
            db_session.delete(seq)
            db_session.commit()

    @staticmethod
    def updateSequence(sequence_id: int, data: Dict) -> StreetviewSequence:
        """
        Update a Streetview Sequence.
        :param sequence_id: int
        :param data: Dict
        :return: StreetviewSequence
        """
        sequence = StreetviewService.getSequence(sequence_id)

        for key, value in data.items():
            setattr(sequence, key, value)
        db_session.commit()

        return sequence
