#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei; Mike'

from protocol.znldProtocol import Protocol
from gui.znldGUI import Application
from libs.myException import *

import binascii
from time import sleep
import json
import logging
import logging.config
logger = logging.getLogger(__name__)

class ZNLDApp(Application):
    def __init__(self):
        self.rc = Protocol(id=id, role=role, hop=hop, baudrate=e32_baudrate)
        self.rc.setName('Thread RC receiving')
        self.rc.setDaemon(True)
        self.rc.start()
        Application.__init__(self)

    def __del__(self):
        logger.debug('Waiting for thread end')
        self.rc.join()
        logger.debug('End')


    def on_all_lamps_on_button_click(self):
        '''灯具全部开'''
        logger.info('on_all_lamps_on_button_click')
        mesg = Protocol.LampControl.BYTE_ALL_ON + '\xFF\xFF'
        logger.info('broadcast mesg = %s' % binascii.b2a_hex(mesg))
        self.rc.RC_lamp_ctrl(Protocol.LampControl.BROADCAST_ID, mesg)
        pass

    def on_all_lamps_off_button_click(self):
        '''灯具全部关'''
        logger.info('on_all_lamps_off_button_click')
        mesg = Protocol.LampControl.BYTE_ALL_OFF + '\xFF\xFF'
        logger.info('broadcast mesg = %s' % binascii.b2a_hex(mesg))
        self.rc.RC_lamp_ctrl(Protocol.LampControl.BROADCAST_ID, mesg)
        pass

    def on_lamp_status_query_button_click(self, lamp_num):
        '''灯具状态查询'''
        logger.debug("Lamp #" + str(lamp_num) + " status query on-going")
        pass

    def on_lamp_status_set_button_click(self, lamp_num):
        '''灯具状态设置'''
        logger.debug("Lamp #" + str(lamp_num) + " status set on-going")
        pass

    def on_lamp_set_slider_move(self, value, lamp_num):
        '''灯具状态设置'''
        logger.debug("Lamp #" + str(lamp_num) + "  " + str(value) + " slider set on-going")
        pass

    def on_lamp_status_set_checkbutton_click(self, lamp_num, status):
        '''维修模式灯具状态设计'''
        logger.debug("Lamp #" + str(lamp_num) + "checkbotton status = " + str(status))
        if status == 1:
            mesg = Protocol.LampControl.BYTE_ALL_ON + '\xFF\xFF'
        else:
            mesg = Protocol.LampControl.BYTE_ALL_OFF + '\xFF\xFF'
        station_id = '\x00' * 5 + chr(lamp_num + 2)
        logger.info('unicast to STA (%s) mesg = %s' % (binascii.b2a_hex(station_id), binascii.b2a_hex(mesg)))
        self.rc.RC_lamp_ctrl(station_id, mesg)
        pass


def logger_init():
    ''' logging configuration in code, which is not in use any more.
    instead we are using dictConfig.
    '''
    from time import localtime, strftime
    log_filename = strftime("test-%y%m%d-%H:%M:%S.log", localtime())
    with open('logging_config.json', 'r') as logging_config_file:
        logging_config = json.load(logging_config_file)
        logging_config['handlers']['file']['filename'] = log_filename
        logging.config.dictConfig(logging_config)


if __name__ == "__main__":
    logger_init()
    file_name = 'node_config.json'
    with open(file_name, 'r') as node_config_file:
        node_config = json.load(node_config_file)
        logger.info('%s', node_config)

    try:
        role = node_config['role'].strip().upper()
        id = binascii.a2b_hex(node_config['id'].strip())
    except KeyError:
        logger.error('key errors (role, id) in configuration')
        exit(-1)

    if role == 'RC':
        hop = node_config['hop']
        e32_baudrate = node_config['e32']['baudrate']
        stations = node_config['stations']
        try:
            gui = node_config['gui'].strip().upper()
        except KeyError:
            gui = 'YES'

        if gui == 'NO':
            logger.debug('running in non-GUI mode')
            rc = Protocol(id=id, role=role, hop=hop, baudrate=e32_baudrate)
            rc.setName('Thread RC receiving')
            rc.setDaemon(True)
            results = {}
            for (id, name) in stations.items():
                results[name]['OK'] = 0
                results[name]['ERR_TAG'] = 0
                results[name]['ERR_TO'] = 0
                results[name]['ERR_NACK'] = 0
            try:
                rc.start()
                sleep(1)
                loop = 0
                led_ctrl = 0x3
                while loop < 10000:
                    mesg = chr(led_ctrl) + '\xFF\xFF'
                    logger.info('broadcast led_ctrl = %s' % repr(led_ctrl))
                    #rc.RC_lamp_ctrl('\x00\x00\x00\x00\x00\x02', mesg)
                    rc.RC_lamp_ctrl(Protocol.LampControl.BROADCAST_ID, mesg)
                    sleep(5) # need to consider network delay here given relay node number
                    logger.info('poll led status from each STA:')
                    for (id, name) in stations.items():
                        try:
                            rc.RC_unicast_poll(binascii.a2b_hex(id), chr(led_ctrl))
                        except RxUnexpectedTag:
                            logger.error('RC got unexpected TAG_POLL_ACK from STA')
                            results[name]['ERR_TAG'] += 1
                        except RxTimeOut:
                            logger.debug('RC didn\'t get expected response from STA')
                            results[name]['ERR_TO'] += 1
                        except RxNack:
                            logger.error('NACK is received')
                            results[name]['ERR_NACK'] += 1
                        else:
                            logger.info('RC got expected TAG_POLL_ACK from STA')
                            logger.info('%s (%s) response successfully' % (name, id))
                            results[name]['OK'] += 1
                        sleep(5) # need to consider network delay here given relay node number
                    logger.info('***** loop = %s: %s*****' % (repr(loop), results))
                    loop += 1
                    if led_ctrl == 0x0:
                        led_ctrl = 0x3
                    else:
                        led_ctrl = 0x0
            except KeyboardInterrupt:
                logger.debug('Stopping Thread by Ctrl-C')
                rc.stop()
            except:
                import traceback
                traceback.print_exc()
            finally:
                logger.debug('Waiting for thread end')
                rc.join()
                logger.debug('End')
        else:
            logger.debug('running in GUI mode')
            # 实例化Application
            app = ZNLDApp()
            # 主消息循环:
            app.mainloop()

    elif role == 'STA':
        sta = Protocol(id=id, role=role)
        sta.setName('Thread STA receiving')
        sta.setDaemon(True)
        try:
            sta.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping Thread by Ctrl-C')
            sta.stop()
        except:
            import traceback
            traceback.print_exc()
        finally:
            logger.debug('Waiting for thread end')
            sta.join()
            logger.debug('End')

    elif role == 'RELAY':
        relay = Protocol(id=id, role=role)
        relay.setName('Thread STA receiving')
        relay.setDaemon(True)
        try:
            relay.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping Thread by Ctrl-C')
            relay.stop()
        except:
            import traceback
            traceback.print_exc()
        finally:
            logger.debug('Waiting for thread end')
            relay.join()
            logger.debug('End')

    else:
        logger.error('role mistake in configuration!')
