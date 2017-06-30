#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei; Mike'

from protocol.znldProtocol import Protocol, LampControl, ZnldCmd
from gui.znldGUI import *
from libs.myException import *

import binascii
from time import sleep
import json
import logging
import logging.config
logger = logging.getLogger(__name__)

class ZNLDApp(Application):
    def __init__(self, stations):
        self.rc = Protocol(id=id, role=role, hop=hop, baudrate=e32_baudrate,
                           testing = testing, timeout = timeout, e32_delay = e32_delay, relay_delay = relay_delay,
                           relay_random_backoff = relay_random_backoff, stations=stations,
                           daemon=True, name='Routine RC receiving')
        self.rc.start()
        self.p_cmd = self.rc.get_cmd_pipe()
        self.stations = self.rc.get_stas_dict() # get stations dict proxy reference in multiprocess env
        Application.__init__(self, self.stations)

    def __del__(self):
        logger.debug('Waiting for routine end')
        #TODO: how to clear pipe & queue on destroy
        # if self.p_cmd.poll(3):
        #     self.p_cmd.recv()
        self.rc.stop()
        self.rc.join()
        logger.debug('End')


    def on_all_lamps_on_button_click(self):
        '''灯具全部开'''
        logger.debug('on_all_lamps_on_button_click')
        cmd = ZnldCmd()
        cmd.dest_id = LampControl.BROADCAST_ID
        cmd.dest_addr = 0
        cmd.cmd = ZnldCmd.CMD_LAMPCTRL
        cmd.message = LampControl.MESG_LAMP_ALL_ON
        self.p_cmd.send(cmd)
        if self.p_cmd.recv().cmd_result:
            logger.debug('Successfully broadcast mesg(%d): %s' % (cmd.cmd_id, binascii.b2a_hex(cmd.message)))
        else:
            logger.error('Unsuccessfully broadcast mesg(%d): %s' % (cmd.cmd_id, binascii.b2a_hex(cmd.message)))

    def on_all_lamps_off_button_click(self):
        '''灯具全部关'''
        logger.debug('on_all_lamps_off_button_click')
        cmd = ZnldCmd()
        cmd.dest_id = LampControl.BROADCAST_ID
        cmd.dest_addr = 0
        cmd.cmd = ZnldCmd.CMD_LAMPCTRL
        cmd.message = LampControl.MESG_LAMP_ALL_OFF
        self.p_cmd.send(cmd)
        if self.p_cmd.recv().cmd_result:
            logger.debug('Successfully broadcast mesg(%d): %s' % (cmd.cmd_id, binascii.b2a_hex(cmd.message)))
        else:
            logger.error('Unsuccessfully broadcast mesg(%d): %s' % (cmd.cmd_id, binascii.b2a_hex(cmd.message)))

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

    def on_lamp_confirm_button_click(self):
        """维修模式灯具确认"""
        node_addr = int(self.frames[PageThree].spinboxes[2].get()) + \
                    int(self.frames[PageThree].spinboxes[1].get()) * 10 + \
                    int(self.frames[PageThree].spinboxes[0].get()) * 100

        lamp1_val = self.frames[PageThree].var1.get()
        lamp2_val = self.frames[PageThree].var2.get()
        if lamp1_val > 0 and lamp2_val > 0:
            lamp_on = LampControl.BYTE_ALL_ON
        elif lamp1_val > 0 and lamp2_val == 0:
            lamp_on = LampControl.BYTE_LEFT_ON
        elif lamp1_val == 0 and lamp2_val > 0:
            lamp_on = LampControl.BYTE_RIGHT_ON
        else:
            lamp_on = LampControl.BYTE_ALL_OFF

        cmd = ZnldCmd()
        cmd.cmd = ZnldCmd.CMD_LAMPCTRL
        cmd.dest_addr = node_addr
        cmd.message = LampControl.TAG_LAMP_CTRL + lamp_on + chr(lamp1_val) + chr(lamp2_val) + LampControl.BYTE_RESERVED

        for id in self.stations.keys():
            if self.stations[id]['addr'] == node_addr:
                logger.debug('unicast to STA (%s) mesg: %s' % (id, binascii.b2a_hex(cmd.message)))
                #cmd.dest_id = binascii.a2b_hex(id)
                break

        self.p_cmd.send(cmd)
        if self.p_cmd.recv().cmd_result:
            logger.debug('got correct response')
        else:
            logger.error('got no or incorrect response')

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
        testing = node_config['testing'].strip().upper()
        timeout = node_config['timeout']
        e32_delay = node_config['e32_delay']
        relay_delay = node_config['relay_delay']
        relay_random_backoff = node_config['relay_random_backoff']
        try:
            gui = node_config['gui'].strip().upper()
        except KeyError:
            gui = 'YES'

        if gui == 'NO':
            logger.debug('running in non-GUI mode')
            rc = Protocol(id=id, role=role, hop=hop, baudrate=e32_baudrate,
                          testing=testing, timeout=timeout, e32_delay=e32_delay, relay_delay=relay_delay,
                          relay_random_backoff=relay_random_backoff, stations=stations,
                          daemon=True, name='Routine RC receiving')
            p_cmd = rc.get_cmd_pipe()
            stas_dict = rc.get_stas_dict()
            cmd = ZnldCmd()
            #cmd.dest_id = LampControl.BROADCAST_ID
            cmd.dest_addr = 0
            cmd.cmd = ZnldCmd.CMD_LAMPCTRL
            results = {}
            for id in stations.keys():
                name = stations[id]['name']
                results[name] = {'OK': 0, 'ERR_BC': 0, 'ERR_UC': 0}
            try:
                rc.start()
                loop = 0
                led_ctrl = 0x3
                while loop < 10000:
                    mesg = LampControl.TAG_LAMP_CTRL + chr(led_ctrl) + '\xFF\xFF\x00'
                    cmd.message = mesg
                    logger.info('broadcast led_ctrl = %s' % repr(led_ctrl))
                    p_cmd.send(cmd)
                    p_cmd.recv()
                    # TODO: ? need a delay to avoid broadcast storm
                    #sleep(rc.hop * (rc.e32_delay + rc.relay_random_backoff))
                    logger.info('poll led status from each STA:')
                    for id in stations.keys():
                        name = stations[id]['name']
                        cmd.dest_id = binascii.a2b_hex(id)
                        cmd.message = LampControl.MESG_POLL
                        p_cmd.send(cmd)
                        if p_cmd.recv().cmd_result:
                            if stas_dict[id]['lamp_ctrl'] == stas_dict[id]['lamp_ctrl_status']:
                                logger.info('%s (%s) response successfully' % (name, id))
                                results[name]['OK'] += 1
                            else:
                                logger.error('not get correct lamp status from %s (%s)' % (name, id))
                                results[name]['ERR_BC'] += 1
                        else:
                            logger.error('not get POLL_ACK from %s (%s)' % (name, id))
                            results[name]['ERR_UC'] += 1
                        # need a delay to avoid broadcast storm
                        #sleep(rc.e32_delay + rc.hop * (rc.relay_delay + rc.relay_random_backoff))
                    logger.info('***** loop = %s: %s*****' % (repr(loop), results))
                    loop += 1
                    if led_ctrl == 0x0:
                        led_ctrl = 0x3
                    else:
                        led_ctrl = 0x0
            except KeyboardInterrupt:
                logger.debug('Stopping routine by Ctrl-C')
                rc.stop()
            except:
                import traceback
                traceback.print_exc()
            finally:
                logger.debug('Waiting for routine end')
                rc.join()
                logger.debug('End')
        else:
            logger.debug('running in GUI mode')
            # 实例化Application
            app = ZNLDApp(stations)
            # 主消息循环:
            app.mainloop()

    elif role == 'RELAY' or role == 'STA':
        node = Protocol(id=id, role=role, stations=None, daemon=True, name='Routine STA receiving')
        try:
            node.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping routine by Ctrl-C')
            node.stop()
        except:
            import traceback
            traceback.print_exc()
        finally:
            logger.debug('Waiting for routine end')
            node.join()
            logger.debug('End')

    else:
        logger.error('role mistake in configuration!')
