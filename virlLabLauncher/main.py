from src.ldapExcel.main import *
import requests
from requests.auth import HTTPBasicAuth
from config import *


def get_email(filename):
    import io
    res = []
    try:
        fin = io.open(filename)
    except:
        print ("error opening file")
        return

    for line in fin:
        line = line.strip()
        if  line and  not "@dal.ca" in line:
            email = str(line) + "@dal.ca"
            res.append(email)
    return res


class VirlLaunch():
    def __init__(self, cohort, lab):
        self.cohort = cohort
        self.lab = lab

        self.ready = []
        self.started = []
        self.stopped = []
        self.failed_start = []
        self.failed_stop = []

        self.timeout = 15

        self.proc = LdapExcel()
        self.proc.connect()


    def load_students(self):
        self.ready = []
        self.failed_start = []
        result = self.proc.search_by_group(self.cohort, ['cn', 'uid'])

        if result:
            for entry in result:
                stud_details = entry[0][1]
                name = stud_details['cn'][0]
                uid = stud_details['uid'][0]
                stud_data = (name, uid)
                if stud_data not in self.ready:
                    self.ready.append(stud_data)
            logger.info ("Ready List Initialized")

        else:
            logger.info("Ready List Initialization Error")

        return

    def sanitize_students(self, emails_list):
        temp = []
        for name, email in self.ready:
            if email in emails_list:
                temp.append((name,email))

        logger.info("initial Ready length: {}".format(len(self.ready)))

        self.ready = temp

        logger.info("New Ready length: {}".format(len(self.ready)))

        return

    def _post(self, append_url="", **data):
        auth = HTTPBasicAuth(username, password)
        url = "{}{}".format(base_url, append_url)
        data = data
        response = requests.post(url, auth=auth, data=data, timeout=self.timeout)
        print("URL: %s <<>> Status: %s" % (response.url, response.status_code))
        return response

    def _delete(self, append_url="", **data):
        auth = HTTPBasicAuth(username, password)
        url = "{}{}".format(base_url, append_url)
        data = data
        response = requests.delete(url, auth=auth,  timeout=self.timeout)
        print("URL: %s <<>> Status: %s" % (response.url, response.status_code))
        return response



    def start_sims(self, retry=True):
        """
        Start function to start  a list of student's simulation
        Takes a list of students from the Ready_List, so the load_students should be called first
        """
        success_count = 0
        total = len(self.ready)
        self.failed_start = []

        while len(self.ready) >= 1:
            stud_data = self.ready.pop()
            name, user_id = stud_data
            user_id = user_id.strip()

            url = 'simulations/create/{}'.format(user_id)
            try:
                response = self._post(url, lab=self.lab)
            except:
                logger.critical("Could not get a response from server request")

            if response.status_code == 201:
                if stud_data not in self.started:
                    self.started.append(stud_data)
                success_count += 1
            else:
                if stud_data not in self.failed_start:
                    self.failed_start.append([stud_data,(response.status_code, response)])

        logger.info("SUCCESSFUL: {} out of {} .. request FAILED: {}".format(success_count, total, (total-success_count)))

        if retry==True and self.failed_start:
            logger.warning('Attempting Failed List')
            success_count = 0
            total = len(self.failed_start)
            temp = []

            while len(self.failed_start) >= 1:
                stud_data = self.failed_start.pop()
                name, user_id = stud_data[0]
                user_id = user_id.strip()

                url = 'simulations/create/{}'.format(user_id)

                try:
                    response = self._post(url, lab=self.lab)
                except:
                    logger.critical("Could not get a response from server request")

                if response.status_code == 201:
                    if stud_data not in self.started:
                        self.started.append(stud_data)
                    success_count += 1
                else:
                    temp.append([stud_data[0],(response.status_code, response)])
            if temp:
                self.failed_start.extend(temp)

            logger.info( "SUCCESSFUL: {} out of {} .. request FAILED: {}".format(success_count, total, len(self.failed_start)))

        return


    def stop_sims(self):
        """
        stop function to stop  a list of students simulation
        Takes a list of students from the Ready_List, so the load_students should be called first
        """

        success_count = 0
        total = len(self.ready)

        while len(self.ready) >= 1:

            stud_data = self.ready.pop()
            name, user_id = stud_data
            user_id = user_id.strip()

            sim_id = "{}-{}".format(self.lab, user_id)
            url = 'simulations/{}'.format(sim_id)
            try:
                response = self._delete(url, lab=self.lab)
            except:
                logger.critical("Could not get a response from server request")

            if response.status_code == 204:
                if stud_data not in self.stopped:
                    self.stopped.append(stud_data)
                success_count += 1
            else:
                if stud_data not in self.failed_stop:
                    self.failed_stop.append([stud_data[0], (response.status_code, response)])

        logger.info( "SUCCESSFUL: {} out of {} .. request FAILED: {}".format(success_count, total, len(self.failed_stop)))

        return


    def retry_start_sims(self):

        success_count = 0
        total = len(self.failed_start)

        while len(self.failed_start) >= 1:
            obj = self.failed_start.pop()
            stud_data = obj[0]


            name, user_id = stud_data
            user_id = user_id.strip()

            url = 'simulations/create/{}'.format(user_id)

            try:
                response = self._post(url, lab=self.lab)
            except:
                logger.critical("Could not get a response from server request")


            if response.status_code == 201:
                if stud_data not in self.started:
                    self.started.append(stud_data)
                success_count += 1
            else:
                if stud_data not in self.failed_start:
                    self.failed_start.append([stud_data, (response.status_code, response)])

            logger.info("SUCCESSFUL: {} out of {} .. request FAILED: {}".format(success_count, total, (total - success_count)))

            return

