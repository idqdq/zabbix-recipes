#!/usr/bin/python3
"""
скрипт посылает уведомления в rocketchat
основная настройка требуется в Zabbix

1. в MediaType создать новый тип: rocket.chat connector
тип: скрипт
script name: название этого файла (файл поместить в AlertScriptPath, сделать исполняемым от пользователя zabbix)
добавить два кастомных параметра:
 - {ALERT.SENDTO}
 - {ALERT.MESSAGE}

2. Создать пользователя
в Media в поле SendTo прописать url:
https://rocket.vbrr.ru/hooks/zCxLqnfA55H2dtpki/p482GBCKFW678fFe9oEPehsuw9Ge5Jtku7fwF4vwjbwNkNuX

3. Создать Actions и прописать нижеслежующие строки DefaultMessage:

PROBLEM_TEXT = {"text":"**{HOST.NAME}** [PROBLEM] :sos: - {TRIGGER.NAME}",
                "emoji":":sos:",
                "attachments": [{
                    "color": "#FF0000",
                    "collapsed": true,
                    "title": "*{TRIGGER.NAME}*: ({ITEM.LASTVALUE1})",
                    "text": "",
                    "fields": [
                        {"title": "Важность", "value": "{TRIGGER.SEVERITY}"},
                        {"title": "Время события", "value": "{EVENT.DATE} - {EVENT.TIME}"}
                        ]
                }]
            }

RECOVERY_TEXT = {"text":"**{HOST.NAME}** [OK] :white_check_mark: - {TRIGGER.NAME}",
                "emoji":":white_check_mark:",
                "attachments": [{
                    "color": "#00FF00",
                    "collapsed": true,
                    "title": "*{TRIGGER.NAME}*: ({ITEM.LASTVALUE1})",
                    "text": "",
                    "fields": [
                        {"title": "Важность", "value": "{TRIGGER.SEVERITY}"},
                        {"title": "Время события", "value": "{EVENT.DATE} - {EVENT.TIME}"}
                        {"title": "Продолжительность события", "value": "{EVENT.AGE}"}
                        ]
                }]
            }

ACK_TEXT = {"text":"**{HOST.NAME}** [ACK] :warning: - {TRIGGER.NAME}",
                "emoji":":warning:",
                "attachments": [{
                    "color": "#FFFF00",
                    "collapsed": true,
                    "title": "*{TRIGGER.NAME}*: ({ITEM.LASTVALUE1})",
                    "text": "{USER.FULLNAME} acknowledged problem at {ACK.DATE} {ACK.TIME} with the following message: {ACK.MESSAGE}",
                    "fields": [
                        {"title": "Важность", "value": "{TRIGGER.SEVERITY}"},
                        {"title": "Время события", "value": "{EVENT.DATE} - {EVENT.TIME}"}
                        {"title": "Текущий статус", "value": "{EVENT.STATUS}"}
                        ]
                }]
            }
"""

import sys
import requests

url = sys.argv[1]
data = sys.argv[2]

#debug
with open("/var/log/zabbix/rocket.log", "a") as logfile:
    logfile.write(data)

headers = {'Content-Type': 'application/json; charset=utf-8'}
res = requests.post(url, data=data.encode('utf-8'), headers=headers)