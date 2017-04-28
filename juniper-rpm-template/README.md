If you have a Juniper network gears and want to monitor some SLAs over your network links
you probably come up with an RPM (Real time performance monitoring) solution

This template will help you to transmit RPM values from a Juniper devices to Zabbix

To do that first you have to configure RPM tests on a Juniper boxes
Im my case the config looks as follows:
===================================================================
services {
    rpm {
        probe Bee {
            test Jitter {
                probe-type icmp-ping-timestamp;
                target address 2.2.2.2;
                probe-count 15;
                probe-interval 1;
                test-interval 15;
                source-address 2.2.2.1;
                data-size 1400;
                thresholds {
                    successive-loss 2;
                }
                hardware-timestamp;
            }
        }
        probe GARS {
            test Jitter {
                probe-type icmp-ping-timestamp;
                target address 1.1.1.2;
                probe-count 15;
                probe-interval 1;
                test-interval 15;
                source-address 1.1.1.1;
                data-size 1400;
                thresholds {            
                    successive-loss 2;
                }
                hardware-timestamp;
            }
        }
    }
}
========================================================================

All over steps should be performed on a Zabbix Server

1. move discovery_juniper_rpm.py to your /zabbix/external_scripts/path
in my case (Ubuntu 14.04) it is located in /etc/zabbix/externalscripts/
2. make chmod +x and chown zabbix:zabbix
3. import template template-juniper-rpm.xls
4. apply template to a Juniper host
5. make sure you have a macro {$SNMP_COMMUNITY} set to the host

5 minutes later the discovery script should find RPM items, then hand them over to Zabbix, 
also it will create triggers graphs and even a screen

