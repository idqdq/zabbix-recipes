#!/usr/bin/env python3
"""
the script is a traphandler that is being called from snmptrapd daemon
The script does process port security snmp traps from cisco gears and hand it over to Zabbix.
There are two types of psecurity traps that depends on psecurity violation mode: shutdown or restrict
The trap iso.3.6.1.4.1.9.9.548.0.1.1 (CISCO-ERR-DISABLE-MIB::cErrDisableInterfaceEvent) is sent for a violation of shutdown
The trap iso.3.6.1.4.1.9.9.315.0.0.1 (ciscoPortSecurityMIB::cpsSecureMacAddrViolation ) is sent for a violation of restrict
will call them trap 548 and trap 315 for a sake of clarity 

this is an example of trap 548
------------------------------------------------------------------
catalyst20
UDP: [0.0.0.0]->[192.168.30.20]:-2039
DISMAN-EVENT-MIB::sysUpTimeInstance 338:5:51:38.08
SNMPv2-MIB::snmpTrapOID.0 CISCO-SMI::ciscoMgmt.548.0.1.1
CISCO-SMI::ciscoMgmt.548.1.3.1.1.2.10640.0 9
------------------------------------------------------------------

and this one is an example of trap 315
------------------------------------------------------------------
catalyst27
UDP: [0.0.0.0]->[192.168.30.27]:-13209
DISMAN-EVENT-MIB::sysUpTimeInstance 342:22:17:16.63
SNMPv2-MIB::snmpTrapOID.0 CISCO-PORT-SECURITY-MIB::cpsSecureMacAddrViolation
IF-MIB::ifIndex.10028 Wrong Type (should be INTEGER): 10028
IF-MIB::ifName.10028 FastEthernet0/28
CISCO-PORT-SECURITY-MIB::cpsIfSecureLastMacAddress.10028 0:21:85:58:7e:d9
------------------------------------------------------------------

script first checks if hostname exists in Zabbix (using ZabbixAPI)
and that hostname has an item with the key that match a trapkeyname_ (defined in a config.ini)
 
then it processes traps
for trap 548 it finds out the interface name out of ifIndex (10640 in the first example above) by issuing an snmp query toward the switch.
for trap 315 it retrieves ifName and mac-address

and finally it sends new value (ifName or ifName + mac-address) to the given host and the corresponding key using external zabbix_sender call
"""

import sys, os, re, subprocess
import logging.handlers, shlex
from pysnmp.hlapi import *
from configparser import ConfigParser
from ipaddress import IPv4Address, AddressValueError
#from zabbix.api import ZabbixAPI
from pyzabbix import ZabbixAPI


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
#db_config = read_config(section = 'mysql')

# set logging handler
handler = logging.handlers.WatchedFileHandler(os.environ.get("LOGFILE", logging_config['logfile']))
#formatter = logging.Formatter(logging.BASIC_FORMAT)
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
trapstr = inp.readline()
m = re.search("\[(.*)\]:[0-9]+->", trapstr)
ip = m.group(1)

try:
    ip = str(IPv4Address(ip))
except AddressValueError as val:
    logging.exception("IP network address '%s' is not valid. Discarding trap", val)
    exit(1)

# all other stdin lines contains a trap itself
trapstr = inp.read().rstrip()

logging.debug("hostname is: %s", hostname)
logging.debug("IP address is: %s", ip)
logging.debug("trap info is: %s", trapstr)

if "548.0.1.1" in trapstr:
    mode = "disable"
    trapkeyname = "trapkeyname_disable"

elif "315.0.0.1" in trapstr:
    mode = "restrict"
    trapkeyname = "trapkeyname_restrict"

elif "315.0.0.2" in trapstr:
    mode = "restrict_trunk"
    trapkeyname = "trapkeyname_restrict"

else:
    logging.error("Unknown trap. Discarding ...")
    exit(1)

logging.debug("api_config: %s, %s, %si", api_config['zabbix_url'], api_config['zabbix_user'], api_config['zabbix_passwd'])

#zabbix
zapi = ZabbixAPI(api_config['zabbix_url'])
zapi.session.verify = False
zapi.login(api_config['zabbix_user'], api_config['zabbix_passwd'])
hostid = zapi.host.get(filter={"host": hostname})[0]['hostid']

if not hostid:
    hostid = zapi.hostinterface.get(filter={"ip": ip}, output=['hostid'])[0]['hostid']
    if not hostid:
        logging.error("there is no hostname %s in Zabbix. Discarding trap...", hostname)
        exit(1)
    hostname = zapi.host.get(filter={"hostid": hostid})[0]['host']
    if not hostname:
        logging.error("there is no hostname %s in Zabbix. Discarding trap...", hostname)
        exit(1)
    logging.info("zabbix related device's hostname  = %s", hostname)
logging.info("hostid = %s", hostid)

key = zapi.item.get(filter={'hostid': hostid, 'key_': 'ErrRestrict'}, output=['key_', 'itemid', 'name'])[0]['key_']
if not key:
    logging.error("there is no suitable items for hostname %s in Zabbix. Discarding trap...", hostname)
    exit(1)
logging.debug("keyname = %s", key)

# now parsing the trap information
traplist = trapstr.split()

if mode is "disable":
    # Now lets find out an interface name (ifName)
    # for the errdisable traps it can always be found within a penultimate word
    trapvalue = traplist[-2]
    logging.debug("trapvalue = %s", trapvalue)

    # now fetch ifindex from a trapvalue by splitting trapvalue with dots "." into a list and taking a penultimate list value
    ifIndex = trapvalue.split(".")[-2]
    logging.debug("ifIndex = %s", ifIndex)

    # find ifName by ifIndex
    logging.debug("snmp community = %s", snmp_config['community'])

    ifName = find_ifDesc_from_ifIndex(ip, ifIndex, snmp_config['community'])
    logging.info("ifName = %s", ifName)

elif mode is "restrict":
    ifName = traplist[7].strip('"')
    mac = ':'.join(traplist[-7:-1]).strip('"')
    logging.info("ifName = %s; mac = %s", ifName, mac)

elif mode is "restrict_trunk":
    ifName = traplist2[5].strip('"')
    mac = ':'.join(traplist2[-7:-1]).strip('"')
    logging.info("ifName = %s; mac = %s", ifName, mac)
    

if ifName:
    # Zabix has a limitation (20 chars) of lenght of values that are being shown in LastValues and LastIssues sections of a FrontEnd
    # lets strip FastEthernet0/2 to Fa0/2 and GigabitEthernet3/0/45 to Gi3/0/45 for a conviniency
    regex = "[A-Za-z]+(\d+\/.*\d+)$"
    m = re.search(regex, ifName)
    if "Gigabit" in ifName:
        ifName = "Gi" + m.group(1)
    elif "Fast" in ifName:
        ifName = "Fa" + m.group(1)
else:
    ifName = "Interface"


# Now send value (ifName or iName + mac) for a given hostname and a key to Zabbix
# --zabbix-server ZABBIX_SERVER --port ZABBIX_PORT --host hostname --key keyname --value keyvalue;

zabbix_sender = zabbix_config['zabbix_sender']
if mode is "disable":
    keyvalue = ifName
elif mode is "restrict":
    keyvalue = ifName + " " + mac   

opt = "--zabbix-server {} --port {} --host {} --key '{}' --value '{}'".format(zabbix_config['server'],zabbix_config['port'], hostname, key, keyvalue)

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

retstr = "portsecurity trap from host {} has been handled successfully".format(hostname)
logging.info(retstr)
