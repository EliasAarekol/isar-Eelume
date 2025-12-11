import logging
from datetime import datetime, timezone
from logging import Logger
from queue import Queue
import random
from threading import Thread
from concurrent import futures
import concurrent.futures
import time
from typing import Callable, List, Optional
from alitra import Position

from robot_interface.models.exceptions.robot_exceptions import (
    RobotCommunicationException,
    RobotNoMissionRunningException,
    RobotAlreadyHomeException,
    RobotInfeasibleMissionException,
    RobotException,
    RobotMissionStatusException,
    RobotActionException,
    RobotRetrieveInspectionException,
)
from robot_interface.models.inspection.inspection import Inspection
from robot_interface.models.mission.mission import Mission
from robot_interface.models.mission.status import MissionStatus, RobotStatus, TaskStatus
from robot_interface.models.mission.task import (
    InspectionTask,
    RecordAudio,
    TakeCO2Measurement,
    TakeImage,
    TakeThermalImage,
    TakeThermalVideo,
    TakeVideo,
    TaskTypes,
)
from robot_interface.models.robots.media import MediaConfig
from robot_interface.robot_interface import RobotInterface
from robot_interface.telemetry.mqtt_client import MqttTelemetryPublisher

from isar_eelume import inspections, telemetry
from isar_eelume.config.settings import settings
from isar_eelume.eelink_sim import EeLinkSim


class Robot(RobotInterface):
    def __init__(self) -> None:
        self.Ee_client = EeLinkSim()
        self.logger = logging.getLogger("ISAR - Eelume")
        self.logger.info("hello from ISAR")

    def mission_feasible(self, mission: Mission) -> bool:
        self.logger.info("Mission_feasible called")
        return True

    def initiate_mission(self, mission: Mission) -> None:
        self.logger.info("Initatiate mission called")

        if self.Ee_client.is_home() and mission.tasks[0] == TaskTypes.ReturnToHome:
            raise RobotAlreadyHomeException(
                "Can not start mission by returning home, robot is already home."
            )
        if not self.mission_feasible(mission):
            raise RobotInfeasibleMissionException(
                "Can not start mission, mission is infeasible."
            )

        if self.Ee_client.running():
            raise RobotException(
                "Can not start new mission, mission is already running"
            )

        self.Ee_client.initiate_mission(mission)

    # add error handling based on how the function throws execptions
    def mission_status(self, mission_id):
        # self.logger.info(
        #     f"Mission status is {self.Ee_client.mission_status(mission_id)}"
        # )
        return self.Ee_client.mission_status(mission_id)

        # TIMEOUT_TIME = 1 # second
        # with futures.ThreadPoolExecutor() as executor:
        #     future = executor.submit(self.sim.mission_status(mission_id))
        #     try:
        #         status = future.result(timeout=TIMEOUT_TIME)
        #     except TimeoutError:
        #         raise RobotCommunicationException
        #     except:
        #         raise RobotMissionStatusException
        # if status is None:
        #     raise RobotException
        # return status

        # status_call = Thread(
        #     target= self.sim.mission_status(mission_id)
        #     )
        # status_call.start()
        # status_call.join(timeout=TIMEOUT_TIME)

        # if th

    # Error handling here
    def stop(self) -> None:
        self.logger.info("stop called")

        robot_status = self.Ee_client.robot_status()
        if not robot_status == RobotStatus.Busy:
            raise RobotNoMissionRunningException(
                "Could not stop mission - No mission running"
            )
        self.Ee_client.stop()

    # might actually change this into actually extracting the inspection type and using the api to get it
    def get_inspection(self, task: InspectionTask) -> Inspection:
        self.logger.info("get_inspection called")

        try:
            inspection = self.Ee_client.get_inspection(task)
        except Exception as e:
            raise RobotRetrieveInspectionException(
                "Could not retrieve task, API call failed with message " + e
            )
        return inspection

    def register_inspection_callback(
        self, callback_function: Callable[[Inspection, Mission], None]
    ) -> Optional[Thread]:
        self.logger.info("Register inspection callback called")

        if settings.SHOULD_SIMULATE_INSPECTION_CALLBACK_CRASH:
            return None

        def inspection_handler_with_crash():
            crash_after = random.randint(10, 60)  # Random between 10-60 seconds
            self.logger.info(
                f"Inspection callback thread started - will crash after {crash_after} seconds"
            )
            time.sleep(crash_after)
            self.logger.warning("Inspection callback thread crashing now...")

        thread = Thread(
            target=inspection_handler_with_crash,
            name="Inspection Callback Handler",
            daemon=True,
        )
        return thread

    def initialize(self) -> None:
        self.logger.info("Initialized called")

        return

    def task_status(self, task_id: str) -> TaskStatus:
        # self.logger.info("Task status called")
        return self.Ee_client.task_status(task_id)

    # def _get_pose_telemetry(self, isar_id: str, robot_name: str) -> str:

    # def _get_battery_telemetry(self, isar_id: str, robot_name: str) -> str:

    def get_telemetry_publishers(
        self, queue: Queue, isar_id: str, robot_name: str
    ) -> List[Thread]:
        raise NotImplementedError()

    # Expand error handling
    def robot_status(self) -> RobotStatus:
        # self.logger.info("Robot status called")

        return self.Ee_client.robot_status()

    # Expand error handling might just say that this isnt a possible function
    def pause(self) -> None:
        self.logger.info("Pause called")

        robot_status = self.Ee_client.robot_status()
        if robot_status == RobotStatus.Paused:
            raise RobotException("Could not pause mission - Mission already paused")
        if not robot_status == RobotStatus.Busy:
            raise RobotNoMissionRunningException(
                "Could not pause mission - No mission running"
            )
        self.Ee_client.pause_mission()

    # Expand error handling
    def resume(self) -> None:
        self.logger.info("REsume called")

        robot_status = self.Ee_client.robot_status()
        if not robot_status == RobotStatus.Paused:
            raise RobotException(
                "Could not resume mission - no currently paused mission"
            )
        self.Ee_client.resume()

    def generate_media_config(self) -> Optional[MediaConfig]:
        raise NotImplementedError()

    # Expand error handling
    # This tries to put the robot/state_machine into a charging state, but thats probably not very relevant for Eelume. ISAR wont nesc be able to tell the Eelume to goto charge
    def get_battery_level(self):
        # self.logger.info("get_batter_level called")

        return self.Ee_client.battery_level()
