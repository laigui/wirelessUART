#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

import json
import logging
import logging.config
logger = logging.getLogger(__name__)

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
        id = node_config['id'].strip().upper()
    except KeyError:
        logger.error('key errors (role, id) in configuration')
        exit(-1)
    if role == 'RC':
        logger.debug('role is RC')
        try:
            gui = node_config['gui'].strip().upper()
        except KeyError:
            gui = 'YES'
        if gui == 'NO':
            logger.debug('running in non-GUI mode')
        else:
            logger.debug('running in GUI mode')

        stations = node_config['stations']
        for (id, name) in stations.items():
            logger.debug('%s: %s' % (id, name))
    elif role == 'STA':
        logger.debug('role is STA')
    elif role == 'RELAY':
        logger.debug('role is RELAY')
    else:
        logger.error('role mistake in configuration!')