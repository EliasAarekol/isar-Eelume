import logging
import random
import time
from threading import Event, Thread

from robot_interface.models.exceptions.robot_exceptions import (
    RobotTaskStatusException,
    RobotMissionStatusException,
    RobotNoMissionRunningException,
    RobotCommunicationException,
    RobotCommunicationTimeoutException,
)
from robot_interface.models.mission.mission import Mission
from robot_interface.models.mission.status import MissionStatus, TaskStatus, RobotStatus
from robot_interface.models.mission.task import ReturnToHome

from isar_eelume.config.settings import settings

# Want this to look like an API wrapper
# Imagine we have a program running on the Eelume top side computer, which is connecting us to Eelink through an API
# We dont know the functionalities of Eelink yet so either we'll get access to basic Eelink functions here, or we'll do that in the program on the topside computer
# Not that important to figure out now, can do that later. Just make an example to start with
# Imagine that we are trying to talk with Eelink

API_DELAY = 0
API_FAIL_PROB = 0
API_TIMEOUT_PROB = 0
API_TIMEOUT_TIME = 0
TASK_TIME = 10
DOCKING_TIME = 5
class EeLinkSim():
    def __init__(self):
        # super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.missions = {}
        self.cur_mission = None
        self.execution = None
        self.signal_resume_mission = Event()
        self.signal_resume_mission.set()
        self.signal_stop_mission = Event() 
        # self.signal_stop_mission = False
        self.execution = Thread()
        task_statuses = None
        self.var_is_home = True
        self.battery = 100
        self.logger = logging.getLogger("isar eelume mission simulation")
        self.logger.info("hello from SIMULATION")


        



    def run(self):
        n_tasks = len(self.cur_mission.tasks)
        cur_task = self.cur_mission.tasks[0]
        cur_task.status = TaskStatus.InProgress
        task_counter = 0
        eloped_time = 0
        t_start = time.time()
        while not self.signal_stop_mission.is_set():
            if task_counter == n_tasks:
                break
            cur_task = self.cur_mission.tasks[task_counter]
            # cur_task.status = TaskStatus.InProgress
            time.sleep(0.25)
            eloped_time += time.time() - t_start
            if not self.signal_resume_mission.is_set():
                cur_task.status = TaskStatus.Paused
                self.signal_resume_mission.wait()
                cur_task.status = TaskStatus.InProgress
            t_start = time.time()
            if eloped_time > TASK_TIME:
                eloped_time = 0
                cur_task.status = TaskStatus.Successful
                task_counter += 1

                self.battery = 100*(1-task_counter/len(self.cur_mission.tasks)/2 )

        self.cur_mission.status = MissionStatus.Successful
        time.sleep(DOCKING_TIME)
        self.var_is_home = True
        self.logger.info(f"Mission with id {self.cur_mission.id} finished")

        



        
    def task_status(self, task_id : int) -> TaskStatus:
        status = next(task.status for task in self.cur_mission.tasks if task.id == task_id)
        if status is None:
            raise RobotTaskStatusException(
                "Task ID did not match any ongoing tasks"
            )
        return status
    
    def initiate_mission(self, mission : Mission) -> None:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        self.signal_resume_mission = Event()
        self.signal_resume_mission.set()
        self.signal_stop_mission = Event() 
        self.var_is_home = False
        self.battery = 100

        self.missions[mission.id] = mission
        self.cur_mission = mission
        # task_statuses: list[TaskStatus] = list(
        #     map(lambda _: TaskStatus.NotStarted, mission.tasks)
        # )
        self.execution = Thread(target=self.run)
        self.execution.start()
        self.logger.info(f"Starting mission: {mission.id}" )

    def is_home(self) -> bool:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)

        return self.var_is_home

    # Might move this into the interface, not sure if want it to be part of the api
    def mission_feasible(self,mission : Mission) -> bool:
        pass

    def running(self) -> bool:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        return self.execution.is_alive()


    def mission_status(self,mission_id : int) -> MissionStatus:
        # self.logger.info(
        #     "Mission status called"
        # )
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        task_statuses : list[TaskStatus] = [task.status for task in self.cur_mission.tasks]
        if not self.signal_resume_mission.wait(0):
            return MissionStatus.Paused
        if all(map(lambda status: status == TaskStatus.NotStarted, task_statuses)):
            return MissionStatus.NotStarted
        if self.execution.is_alive():
            return MissionStatus.InProgress
        if all(map(lambda status: status == TaskStatus.Successful, task_statuses)):
            return MissionStatus.Successful
        if any(
            map(
                lambda status: status in [TaskStatus.InProgress, TaskStatus.NotStarted],
                task_statuses,
            )
        ):
            return MissionStatus.InProgress
        if all(map(lambda status: status == TaskStatus.Failed, task_statuses)):
            return MissionStatus.Failed
        if any(map(lambda status: status == TaskStatus.Cancelled, task_statuses)):
            return MissionStatus.Cancelled
        if any(map(lambda status: status == TaskStatus.Failed, task_statuses)):
            return MissionStatus.PartiallySuccessful


    def stop(self) -> None:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        if not self.execution.is_alive():
            raise RobotNoMissionRunningException(
                "Cannot stop mission - No misson running"
            )
        self.logger.info("Mission stopping")
        self.signal_stop_mission.set()

    def robot_status(self) -> RobotStatus:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        if not self.signal_resume_mission.is_set():
            # self.logger.info("Robot is paused")

            return RobotStatus.Paused
        elif self.var_is_home:
            # self.logger.info("Robot is Home")
            return RobotStatus.Home
        elif self.execution.is_alive():
            # self.logger.info("Robot is busy")
            return RobotStatus.Busy
        else:
            # self.logger.info("Robot is available")
            return RobotStatus.Available 


    def pause_mission(self) -> None:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        self.logger.info("Pausing mission")
        self.signal_resume_mission.clear()

    def resume(self) -> None:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        self.logger.info("Resuming mission")
        self.signal_resume_mission.set()

    def battery_level(self) -> float:
        self._sim_api_call(API_DELAY,API_FAIL_PROB,API_TIMEOUT_PROB,API_TIMEOUT_TIME)
        # self.logger.info("battery level called")

        return self.battery

    #Simulate the time it takes for the apicall to complete
    def _sim_api_delay(self,delay : int) -> None:
        time.sleep(delay)

    def _sim_api_fail(self,prob : float) -> None:
        if random.random() < prob:
            raise RobotCommunicationException("" \
            "API call failed due to internal error"
            )
    
    def _sim_api_timeout(self, prob : float, timeout : int) -> None:
            if random.random() < prob:
                time.sleep(timeout)
                raise RobotCommunicationTimeoutException(
                    "API call timed out"
                )
    
    def _sim_api_call(
            self,
            delay : int,
            fail_prob : float,
            timeout_prob : float,
            timeout : int
            ) -> None:
        self._sim_api_delay(delay)
        self._sim_api_fail(fail_prob)
        self._sim_api_timeout(timeout_prob,timeout)

