#!/usr/bin/env python
"""
the script is a traphandler that is being called from an snmptrapd daemon
script does process snmp err-disable traps from cisco gears and hand it over to Zabbix.
Traps comes from snmptrapd in one of the following formats:
------------------------------------------------------------------
catalyst20
UDP: [0.0.0.0]->[192.168.30.20]:-2039
DISMAN-EVENT-MIB::sysUpTimeInstance 338:5:51:38.08
SNMPv2-MIB::snmpTrapOID.0 CISCO-SMI::ciscoMgmt.548.0.1.1
CISCO-SMI::ciscoMgmt.548.1.3.1.1.2.10640.0 9
------------------------------------------------------------------
catalyst27
UDP: [0.0.0.0]->[192.168.30.27]:-13209
DISMAN-EVENT-MIB::sysUpTimeInstance 342:22:17:16.63
SNMPv2-MIB::snmpTrapOID.0 CISCO-PORT-SECURITY-MIB::cpsSecureMacAddrViolation
IF-MIB::ifIndex.10028 Wrong Type (should be INTEGER): 10028
IF-MIB::ifName.10028 FastEthernet0/28
CISCO-PORT-SECURITY-MIB::cpsIfSecureLastMacAddress.10028 0:21:85:58:7e:d9
------------------------------------------------------------------
catalyst22
UDP: [0.0.0.0]->[192.168.30.22]:-11723
DISMAN-EVENT-MIB::sysUpTimeInstance 3:55:03.20
SNMPv2-MIB::snmpTrapOID.0 CISCO-PORT-SECURITY-MIB::cpsTrunkSecureMacAddrViolation
IF-MIB::ifName.10002 FastEthernet0/2
CISCO-VTP-MIB::vtpVlanName.1.64 PRINTERS
CISCO-PORT-SECURITY-MIB::cpsIfSecureLastMacAddress.10002 0:15:99:64:f5:2f
------------------------------------------------------------------

script first checks if hostname exists in Zabbix (using ZabbixAPI)
second it finds the key that handles traps (defined in a trapkeyname config option)
then convert ifIndex (10640 in the first example above) to ifName by issuing an snmp query toward the catalyst
and finally puts ifName and key parameters to the given host using external zabbix_sender calls 
"""

import sys, os, re, subprocess
import ipaddress, logging.handlers, shlex
from pysnmp.hlapi import *
from configparser import ConfigParser
from zabbix.api import ZabbixAPI
#from mysql.connector import MySQLConnection, Error

def read_config(filename, section):
    """ Read a configuration file and return a dictionary object
    :param filename: name of the configuration file
    :param section: section of a configuration
    :return: a dictionary of a configfile section parameters
    """
    # create parser and read ini configuration file
    parser = ConfigParser()
    parser.read(filename)

    # get section
    db = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            db[item[0]] = item[1]
    else:
        raise Exception('{0} not found in the {1} file'.format(section, filename))

    return db

def find_ifDesc_from_ifIndex(hostname, ifIndex, community="publices"):
    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(SnmpEngine(),
               CommunityData(community),
               UdpTransportTarget((hostname, 161)),
               ContextData(),
               ObjectType(ObjectIdentity('IF-MIB', 'ifDescr', ifIndex)))
    )

    if errorIndication:
        logging.error(errorIndication)
    elif errorStatus:
        logging.error('%s at %s', errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex) - 1][0] or '?')
        exit(1)
    else:
        ifDescr = varBinds[0][1].prettyPrint()
        return ifDescr

# find the path where the script is located to find a config.ini nearby
dir_path = os.path.dirname(os.path.realpath(__file__))
conf_file_name = dir_path + '/config.ini'

# fetch config parameters
snmp_config = read_config(conf_file_name, section = 'snmp')
api_config = read_config(conf_file_name, section = 'api')
logging_config = read_config(conf_file_name, section = 'logging')
zabbix_config = read_config(conf_file_name, section='zabbix')

# set logging handler
handler = logging.handlers.WatchedFileHandler(os.environ.get("LOGFILE", logging_config['logfile']))
formatter = logging.Formatter( '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root = logging.getLogger()
root.setLevel(os.environ.get("LOGLEVEL", logging_config['loglevel']))
root.addHandler(handler)

# now parse the stdin
inp = sys.stdin

# the first line is alwats hostname
hostname = inp.readline().strip()

# the second line contains an IP address that should be fetched by regexp
str = inp.readline()
m = re.search("\[(.*)\]:[0-9]+->", str)
ip = m.group(1)

try:
    ipaddress.ip_network(unicode(ip))
except:
    logging.exception("IP network address '%s' is not valid. Discarding trap", val)
    exit(1)

# all other stdin lines contains a trap itself
trapstr = inp.read().rstrip()

logging.debug("hostname is: %s", hostname)
logging.debug("IP address is: %s", ip)
logging.debug("trap info is: %s", trapstr)

logging.debug("api_config: %s, %s, %si", api_config['zabbix_url'], api_config['zabbix_user'], api_config['zabbix_passwd'])

# using ZabbixAPI check if a hostname and a corresponding item exists
z = ZabbixAPI(api_config['zabbix_url'], user=api_config['zabbix_user'], password=api_config['zabbix_passwd'])

hostid = z.get_id("host", item=hostname)
if not hostid:
    # device's hostname may not match to the one in zabbix
    # in this case try to find out a hostname by the device's ipaddress
    res = z.hostinterface.get(search={'ip':ip}, output=['hostid','interfaceid'])
    if not res:
        logging.error("there is no hostname %s in Zabbix. Discarding trap...", hostname)
        exit(1)

    hostid = res[0]['hostid']

    res = z.host.get(hostids=hostid, output=['hostid','name'])
    if not res:
        logging.error("there is no hostname %s in Zabbix. Discarding trap...", hostname)
        exit(1)

    hostname = res[0]['name']
    logging.info("zabbix related device's hostname  = %s", hostname)

logging.info("hostid = %s", hostid)

res = z.item.get(hostids=hostid, search={'key_':zabbix_config['trapkeyname']}, output=['itemid','name', 'key_'])
if not res:
    logging.error("there is no suitable items for hostname %s in Zabbix. Discarding trap...", hostname)
    exit(1)

key = res[0]['key_']
logging.debug("keyname = %s", key)


# Now lets find an interface name (ifName)
# retrieve trapkey and trapvalue elements from a trapvalue string
# for SNMPv2-MIB::snmpTrapOID type traps they seems to be always 3rd and penultimate words respectively
traplist = trapstr.split()
trapkey = traplist[3]
trapvalue = traplist[-2]
logging.debug("trapkey = %s", trapkey)
logging.debug("trapvalue = %s", trapvalue)

# fetch ifindex from a trapvalue by splitting trapvalue with dots "." into a list and taking a penultimate list value
ifIndex = trapvalue.split(".")[-2]
logging.debug("ifIndex = %s", ifIndex)

# find ifName by ifIndex
logging.debug("snmp community = %s", snmp_config['community'])

ifName = find_ifDesc_from_ifIndex(ip, ifIndex, snmp_config['community'])
logging.info("ifName = %s", ifName)

if ifName:
    # Zabix has a limitation (20 chars) of lenght of values that are being shown in LastValues and LastIssues sections of a FrontEnd
    # lets strip ifNames so names like FastEthernet0/2 and GigabitEthernet3/0/45 become Fa0/2 and Gi3/0/45 accordingly
    if (len(ifName) > 20):
        regex = "[A-Za-z]+(\d+\/.*\d+)$"
        m = re.search(regex, ifName)
        if "Gigabit" in ifName:
            ifName = "Gi" + m.group(1)
        elif "Fast" in ifName:
            ifName = "Fa" + m.group(1)
else:
    ifName = "Interface"


# Now send value ifName for a given hostname and an keyname to Zabbix
# --zabbix-server ZABBIX_SERVER --port ZABBIX_PORT --host hostname --key keyname --value ifName;

zabbix_sender = zabbix_config['zabbix_sender']
opt = "--zabbix-server {} --port {} --host {} --key '{}' --value '{}'".format(zabbix_config['server'],zabbix_config['port'], hostname, key, ifName)
mycommand = zabbix_sender + " " + opt
logging.debug("zabbix_sender command: %s", mycommand)

try:
    p = subprocess.Popen(shlex.split(mycommand), stdout=subprocess.PIPE)
    output, err = p.communicate()
    logging.debug(output)
    logging.debug(err)

except subprocess.CalledProcessError as e:
    logging.error(e)
    exit(1)

retstr = "trap {} from host {} has been handled successfully".format(trapkey, hostname)
logging.info(retstr)

