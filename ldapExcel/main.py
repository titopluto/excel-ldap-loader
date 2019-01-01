import os
import logging
import ldap.modlist as modlist
import xlrd
import ldap

import config
from src.ldapExcel.util import unicode_to_str_dict

#initialize the Logger Class
logger = logging.getLogger("ldapExcel")
logger.setLevel(logging.DEBUG)

format = logging.Formatter("%(levelname)s: %(message)s")

streamHandler = logging.StreamHandler()
streamHandler.setFormatter(format)

fileHandler = logging.FileHandler('event-logs.log')
fileHandler.setLevel(logging.INFO)
fileHandler.setFormatter(format)

logger.addHandler(streamHandler)
# logger.addHandler(fileHandler)  ==> if you want to log into a file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



class LdapExcel():
    '''
    A class to initialize an object used to  connect to a LDAP service and perform necessary tasks

    '''
    def __init__(self, exceldoc=""):
        '''

        :param exceldoc: The path to the excel document to be loaded
        '''
        self.url = config.LDAP_URL
        self.root_dn = config.ROOT_DN
        self.password = config.ROOT_PASSWORD
        self.base_dn = config.BASE_DN
        self.group_dn = config.GROUP_DN
        #self.start_uid = START_UID   #disabled to use the function maxuid()+1
        self.proc = None
        self.workbook = None
        self.worksheets = None
        self.exceldoc = exceldoc

        logger.info("The User directory where excel file should be loaded is: ==>{}".format(BASE_DIR))

        if exceldoc:
            try:
                if os.path.exists(os.path.join(BASE_DIR, self.exceldoc)):
                    logger.info(" The Excel document exists and will be referenced")
                else:
                    logger.error ("ERROR!!! Excel document could not be loaded!")

            except:
                logger.error ("ERROR!!! Something went wrong during Excel File initialization")
        else:
            logger.warning("No Excel document was provided, you cannot use the ADD method")


    def connect(self):
        '''
        method use to make a connection to the LDAP server

        :return: None
        '''

        try:
            self.proc = ldap.initialize(self.url)
            self.proc.protocol_version = config.PROTOCOL_VERSION
            self.proc.simple_bind_s(self.root_dn, self.password)

            logger.info ("Successfully connected to server: {server}".format(server=config.LDAP_URL))

        except ldap.LDAPError as error:
            logger.error ("Connection to Server Failed! ==> {error} ".format(error=error))

    def load_data(self):
        '''
        Method to load all sheets in the Excel workbook
        :return: a generator object if successful
        '''
        if self.exceldoc:
            try:
                excel_file = os.path.join(BASE_DIR, self.exceldoc)
                self.workbook = xlrd.open_workbook(excel_file)
                self.worksheets = self.workbook.sheet_names()
                # print "Data loaded successfully.. Number of sheets: %d" %(len(self.worksheets))

                for sheet in self.worksheets:
                    active_sheet = self.workbook.sheet_by_name(sheet)
                    num_rows = active_sheet.nrows
                    num_cols = active_sheet.ncols
                    header = [active_sheet.cell_value(0, cell).lower() for cell in range(num_cols)]
                    for row_idx in range(1, num_rows):
                        row_cell = [active_sheet.cell_value(row_idx, col_idx) for col_idx in range(num_cols)]
                        yield dict(zip(header, row_cell))
                logger.info ("Data loaded successfully.. Number of sheets: {}".format(len(self.worksheets)))
            except:
                logger.error ("Could not load Excel workbook")
        else:
            logger.error("No Excel file loaded during initialization")



    def get_gidnumber(self, group_cn):
        '''
        method to get the GID number of a group cn
        :param group_cn:
        :return: int
        '''
        group_cn = group_cn.strip()
        try:
            dn, entry = self.proc.search_s(group_cn, ldap.SCOPE_BASE)[0]
            return entry['gidNumber'][0]
        except ldap.LDAPError as e:
            logger.error(e)
            return

    def _search(self, searchScope, searchFilter, retrieveAttributes ):
        '''
        Method to make a search query

        :param searchScope:
        :param searchFilter:
        :param retrieveAttributes:

        :return: a list
        '''

        try:
            ldap_result_id = self.proc.search(self.base_dn, searchScope, searchFilter, retrieveAttributes)
            result_set = []
            while True:
                result_type, result_data = self.proc.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)
            # you can loop through result
            return result_set
        except ldap.LDAPError as e:
            logger.exception (e)
            return


    def search_by_group(self, group_name, attr=None):
        '''
        Method to make a search query by group name

        :param group_name:
        :param attr:
        :return: list
        '''
        searchScope = ldap.SCOPE_SUBTREE

        if isinstance(attr, str):
            retrieveAttributes = [attr]
        else:
            retrieveAttributes = attr

        group_name = str(group_name.strip() )
        group_cn = "cn={},{}".format(group_name, self.group_dn)

        gid_number = self.get_gidnumber(group_cn)

        if gid_number == None:
            logger.error("Invalid Group Name supplied")
            return

        searchFilter = "gidNumber={}".format(gid_number)

        return self._search(searchScope, searchFilter, retrieveAttributes)


    def search_by_user(self, uid, attr=None):
        '''
        Method to make a search query by a user cn

        :param uid:
        :param attr:
        :return: list
        '''
        searchScope = ldap.SCOPE_SUBTREE

        if isinstance(attr, str):
            retrieveAttributes = [attr]
        else:
            retrieveAttributes = attr

        uid = str(uid.strip() )
        user_cn = "cn={},{}".format(uid, self.base_dn)

        searchFilter = "uid={}".format(uid)
        return self._search(searchScope, searchFilter, retrieveAttributes)


    def max_uid(self):
        '''
        Method to get the maximum UID in the LDAP database

        :return: int
        '''
        max_uid = 0

        searchScope = ldap.SCOPE_SUBTREE
        retrieveAttributes = None
        searchFilter = "cn=*"

        data = self._search(searchScope, searchFilter, retrieveAttributes)
        logger.info ('Total Entries: {}'.format(len(data)))
        for user in data:
            if int(user[0][1]['uidNumber'][0]) > max_uid:
                max_uid = int(user[0][1]['uidNumber'][0])
        return max_uid

    def add(self):
        '''
        Method to add users from the excel workbook to the LDAP database


        :return:
        '''
        uid = self.max_uid() + 1
        success = 0
        failed = 0
        for user in self.load_data():
            uid += 1
            user['gidnumber'] = [str(int(user['gidnumber']))]
            user['userPassword'] = config.USER_PASSWORD
            user['objectclass'] = config.OBJECT_CLASS
            user['uid'] = user['mail']
            user['uidNumber'] = str(uid)
            user['homeDirectory'] = config.HOME_DIRECTORY + '{}'.format(str(user['givenname']).lower())

            user = unicode_to_str_dict(user)
            user_dn = "cn={},".format(user['cn']) + self.base_dn

            try:
                ldif = modlist.addModlist(user)
                self.proc.add_s(user_dn, ldif)
                logger.info("Added to database ==> {user}".format(user=user['cn']))
                success += 1

            except ldap.LDAPError as error:
                logger.error ("error while adding")
                # logger.error(error)
                logger.error ("{error} ==> {user}".format(error=error, user=user['cn']))
                failed += 1
                uid -= 1  # not tested yet --> modified if code breakes
        print ("last uid: ", uid)
        print ("records added: ", success)
        print ("records failed: ", failed)

    def delete(self, user):
        '''
        Method to delete user from LDAP database
        :param user: user cn

        :return: None
        '''
        deleteDN = "uid=%s" % (user) + self.base_dn
        try:
            self.proc.delete_s(deleteDN)
        except ldap.LDAPError as e:
            logger.error (e)

    def disconnect(self):
        '''
        Method to disconnect gracefully from the LDAP server
        :return:
        '''
        self.proc.unbind_s()
