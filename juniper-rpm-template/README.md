If you have any Juniper network gears and want to monitor some SLAs over your network links
you probably come up with an RPM (Real time performance monitoring) solution

This template will help you to transmit RPM values from a Juniper devices to Zabbix

To do that first you have to configure RPM tests on a Juniper boxes
Im my case the config looks as follows:

```sh
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
```

All over steps should be performed on ypur Zabbix Server

  - move `discovery_juniper_rpm.py` to your /zabbix/external_scripts/path (in my case (Ubuntu 14.04) it is located in /etc/zabbix/externalscripts/)
  - make chmod +x and chown zabbix:zabbix
  - import template `template-juniper-rpm.xls`
  - apply template to a Juniper host
  - make sure you have a macro {$SNMP_COMMUNITY} set to the host

5 minutes later the discovery script should find RPM items and propagate items, triggers, graphs etc for every RPM test

Enjoy

P.S. Take a look at timing on item prototypes. 
Those extremely low intervals were suitable for my case but may not be applicable for you
