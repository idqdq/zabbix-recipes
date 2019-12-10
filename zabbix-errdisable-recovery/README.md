Скрипт разблокировки заблокированных механизмом **PortSecurity** портов на коммутаторах **Cisco** средствами _Zabbix_  
Для чего он нужен написано в статье по [ссылке](http://dokuwiki.msk.vbrr.loc/doku.php?id=monitoring:zabbix_traps_portsecurity#%D0%BE%D1%87%D0%B8%D1%81%D1%82%D0%BA%D0%B0_%D0%B7%D0%B0%D0%B1%D0%BB%D0%BE%D0%BA%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE_%D0%BF%D0%BE%D1%80%D1%82%D0%B0_%D1%81%D1%80%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%B0%D0%BC%D0%B8_zabbix)

## Установка скрипта

1. склонировать файлы из репозитория *git pull/clone ...*
* доставить необходимые пакеты *pip install -r requirements.txt*
* создать файл *defaults/creds.yml* с таким содержимым

    ```yml
    user: cisco
    pass: cisco
    zabbix_url: https://zabbix.acmeloc
    zabbix_user: api
    zabbix_passwd: api
    ```
* создать файл *vault/vault_password* с паролем
* зашифровать *defaults/creds.yml* паролем из *vault/vault_password*:     
    > user@host:~$ ansible-vault encrypt --vault-password-file vault/vault_password defaults/creds.yml
* скопировать все файлы в директорию */etc/zabbix/alertscripts/zabbix-errdisable-recovery/*  
    и затем модифицировать права на файлы выполнив команду:
    > user@host:~$ chown -R zabbix /etc/zabbix/alertscripts/zabbix-errdisable-recovery/
* в веб-морде *Zabbix* создать **Action** и настроить действия в вкладке **Acknowledgement operations** следующим ообразом:
![](../pics/errdisable-recovery-zabbix-ack.png)
    > Строка запуска:   
        /usr/bin/python3 /etc/zabbix/alertscripts/zabbix-errdisable-recovery/clear-portsecurity.py {ITEM.LASTVALUE} {HOST.HOST} {EVENT.ID} {EVENT.STATUS}
