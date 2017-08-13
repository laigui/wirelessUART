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
        self._communication = 0
        Application.__init__(self, self.stations)
        self._update_comm()

    def _update_comm(self):
        self._communication = self.rc.get_comm_status().value
        if (self._communication == 0):
            self._comm_status[0] = '通讯空闲'
        elif (self._communication == 1):
            self._comm_status[0] = '通讯进行中'
        elif (self._communication == 2):
            self._comm_status[0] = '通讯成功'
        else:
            self._comm_status[0] = '通讯失败'
        self.after(1000, func=self._update_comm)

    def __del__(self):
        logger.debug('Waiting for routine end')
        #TODO: how to clear pipe & queue on destroy
        # if self.p_cmd.poll(3):
        #     self.p_cmd.recv()
        self.rc.stop()
        self.rc.join()
        logger.debug('End')

    def _check_cmd_status(self):
        if self.p_cmd.poll():
            if self.p_cmd.recv().cmd_result:
                logger.debug('CMD done SUCCESS!')
            else:
                logger.error('CMD done FAIL!')
        else:
            self.after(1000, self._check_cmd_status)

    def on_all_lamps_on_button_click(self):
        '''灯具全部开'''
        if (self.rc.get_comm_status().value != 1): # not in communication
            logger.debug('on_all_lamps_on_button_click')
            cmd = ZnldCmd()
            cmd.dest_id = LampControl.BROADCAST_ID
            cmd.dest_addr = 0
            cmd.cmd = ZnldCmd.CMD_LAMPCTRL
            cmd.message = LampControl.MESG_LAMP_ALL_ON
            self.p_cmd.send(cmd)
            self._check_cmd_status()

    def on_all_lamps_off_button_click(self):
        '''灯具全部关'''
        if (self.rc.get_comm_status().value != 1): # not in communication
            logger.debug('on_all_lamps_off_button_click')
            cmd = ZnldCmd()
            cmd.dest_id = LampControl.BROADCAST_ID
            cmd.dest_addr = 0
            cmd.cmd = ZnldCmd.CMD_LAMPCTRL
            cmd.message = LampControl.MESG_LAMP_ALL_OFF
            self.p_cmd.send(cmd)
            self._check_cmd_status()

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
        if (self.rc.get_comm_status().value != 1):  # not in communication
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
            cmd.message = LampControl.TAG_LAMP_CTRL + lamp_on + chr(int(lamp1_val*255/100)) \
                          + chr(int(lamp2_val*255/100)) + LampControl.BYTE_RESERVED

            for id in self.stations.keys():
                if self.stations[id]['addr'] == node_addr:
                    logger.debug('unicast to STA (%s) mesg: %s' % (id, binascii.b2a_hex(cmd.message)))
                    #cmd.dest_id = binascii.a2b_hex(id)
                    break

            self.p_cmd.send(cmd)
            self._check_cmd_status()

def logger_init():
    ''' logging configuration in code, which is not in use any more.
    instead we are using dictConfig.
    '''
    from time import localtime, strftime
    from os.path import expanduser
    path = expanduser("~")
    log_filename = os.path.join(path, 'znld-logs', strftime("test-%y%m%d-%H:%M:%S.log", localtime()))
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
        logger.exception('key errors (role, id) in configuration')
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
                    cmd.dest_id = LampControl.BROADCAST_ID
                    logger.info('broadcast led_ctrl = %s' % repr(led_ctrl))
                    p_cmd.send(cmd)
                    p_cmd.recv()
                    logger.info('poll led status from each STA:')
                    for id in stations.keys():
                        name = stations[id]['name']
                        cmd.dest_id = binascii.a2b_hex(id)
                        # if led_ctrl == 0x0:
                        #     led_ctrl = 0x3
                        # else:
                        #     led_ctrl = 0x0
                        # mesg = LampControl.TAG_LAMP_CTRL + chr(led_ctrl) + '\xFF\xFF\x00'
                        mesg = LampControl.MESG_POLL
                        cmd.message = mesg
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
                    logger.info('***** loop = %s: %s*****' % (repr(loop), results))
                    loop += 1
                    if led_ctrl == 0x0:
                        led_ctrl = 0x3
                    else:
                        led_ctrl = 0x0
            except KeyboardInterrupt:
                logger.debug('Stopping routine by Ctrl-C')
                rc.stop()
            except Exception as ex:
                logger.exception(ex)
            finally:
                logger.debug('Waiting for routine end')
                rc.join()
                logger.debug('End')
        else:
            logger.debug('running in GUI mode')
            try:
                # 实例化Application
                app = ZNLDApp(stations)
                # 主消息循环:
                app.mainloop()
            except Exception as ex:
                logger.exception(ex)
                app.rc.terminate()
                raise

    elif role == 'RELAY' or role == 'STA':
        node = Protocol(id=id, role=role, stations=None, daemon=True, name='Routine STA receiving')
        try:
            node.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping routine by Ctrl-C')
            node.stop()
        except Exception as ex:
            logger.exception(ex)
        finally:
            logger.debug('Waiting for routine end')
            node.join()
            logger.debug('End')

    else:
        logger.error('role mistake in configuration!')
