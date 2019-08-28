'''
COPYRIGHT STATUS:
Dec 1st 2001, Fermi National Accelerator Laboratory (FNAL) documents and
software are sponsored by the U.S. Department of Energy under Contract No.
DE-AC02-76CH03000. Therefore, the U.S. Government retains a  world-wide
non-exclusive, royalty-free license to publish or reproduce these documents
and software for U.S. Government purposes.  All documents and software
available from this server are protected under the U.S. and Foreign
Copyright Laws, and FNAL reserves all rights.

Distribution of the software available from this server is free of
charge subject to the user following the terms of the Fermitools
Software Legal Information.

Redistribution and/or modification of the software shall be accompanied
by the Fermitools Software Legal Information  (including the copyright
notice).

The user is asked to feed back problems, benefits, and/or suggestions
about the software to the Fermilab Software Providers.

Neither the name of Fermilab, the  URA, nor the names of the contributors
may be used to endorse or promote products derived from this software
without specific prior written permission.

DISCLAIMER OF LIABILITY (BSD):

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED  WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED  WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL FERMILAB,
OR THE URA, OR THE U.S. DEPARTMENT of ENERGY, OR CONTRIBUTORS BE LIABLE
FOR  ANY  DIRECT, INDIRECT,  INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
OF SUBSTITUTE  GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY  OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE  POSSIBILITY OF SUCH DAMAGE.

Liabilities of the Government:

This software is provided by URA, independent from its Prime Contract
with the U.S. Department of Energy. URA is acting independently from
the Government and in its own private capacity and is not acting on
behalf of the U.S. Government, nor as its contractor nor its agent.
Correspondingly, it is understood and agreed that the U.S. Government
has no connection to this software and in no manner whatsoever shall
be liable for nor assume any responsibility or obligation for any claim,
cost, or damages arising out of or resulting from the use of the software
available from this server.

Export Control:

All documents and software available from this server are subject to U.S.
export control laws.  Anyone downloading information from this server is
obligated to secure any necessary Government licenses before exporting
documents or software obtained from this server.
'''

#!/usr/bin/env python

###############################################################################
#  XrootD Third-party Copy Test Package
#  testsuite.py
#
#  Parent class for the test suite implementations.
#
#  Provides basic API:  configure(), 
#                       configure_multiprocessing(bool), 
#                       run()
#                       wait_for_completion(int)
#  
#  plus abstract methods to implement:  
#                       do_setup(), 
#                       do_main(), 
#                       do_teardown(), 
#                       do_postprocess()
#
#  Also contains implementation (Worker) of the multiprocessor Process class.
# 
###############################################################################

import multiprocessing
import os
import traceback

from time import strftime,gmtime
from ..util.tasks import *
from ..util.reports import *
from ..util.utils import *

class Worker(multiprocessing.Process):
    def __init__(self, id, queue, report, wait_cond):
        super(Worker, self).__init__()
        self.id = id
        self.queue = queue
        self.report = report
        self.wait_cond = wait_cond

    def run(self):
        '''
            Changed to while from the for + iterator because it was
            susceptible to uncaught exceptions thrown during
            the queue.get() which would kill the worker.
        '''
        while True:
            try:
                '''
                    blocks; to stop the worker, we put None in the queue
                '''
                t = self.queue.get()
                if not t:
                    break
            except Exception, e:
                message = str(e)
                print_error("Worker %s caught exception: %s;"%(self.id, message))
                continue

            if not isinstance(t, tasks.Task):
                print_error("Worker %s dequeued %s, but this is not a Task."%(self.id, t))
                continue

            print_message("Worker %s, RUNNING %s: %s"%(self.id, t.id, t.log_file_name))  

            rc = t.run()

            result = {'rc' : rc, 'task' : t}
            
            if self.wait_cond:
                self.wait_cond.acquire()
                self.report['counter'] += 1

            if debug:
                print_message("Worker %s incremented counter to %s"%(self.id, self.report['counter']))

            if rc:
                print_message("Worker %s, FAILURE for %s: %s"%(self.id, t.id, t.log_file_name))
                results = self.report['failure']
                results[t.id] = result
                self.report['failure']= results
            else:
                print_message("Worker %s, SUCCESS for %s: %s"%(self.id, t.id, t.log_file_name))
                results = self.report['success']
                results[t.id] = result
                self.report['success']= results

            if self.wait_cond:
                self.wait_cond.notify_all()
                self.wait_cond.release()

class TestSuite(object):
    def __init__(self, debug, config_file):
        set_global_debug(debug)
        self.debug = debug
        self.config_file = config_file
        self.config = None
        self.endpoints = None
        self.manager = None
        self.report = None
        self.queue = None
        self.wait_cond = None
        self.workers = []
        self.cpu_count = 0
        self.ref_endpoint = None
        self.ref_end_id = None
    
    def __repr__(self):
        return str(self.__class__)

    def configure(self):
        if not (os.path.isfile(self.config_file)):
            print_error("No configuration file found; default path is " 
            + "./xrootdtest.json; or provide path as command-line option (-f).")
            return 1

        print_message("Using config file: %s"%self.config_file)
        self.config = load_json_configuration(self.config_file)
        if not self.config:
            return 2

        print_message("Validating configuration ...")
        if validate_configuration(self.config):
            return 3

        self.config['run-timestamp'] = "%s"%strftime("%Y%m%d%H%M%S", gmtime())

        print_message("Preparing test environment ...")
        if prepare_environment(self.config):
            return 4

        self.config['xrootd-settings']['version'] \
            = get_version(get_dict_value(['xrootd-settings', 'xrdcp'], self.config))
            
        print_message("Checking for data file ...")
        if generate_data_file(self.config):
            return 5

        self.endpoints = get_dict_value(['endpoints'], self.config)
        names = get_endpoint_names(self.endpoints)
        print_message("Using the following endpoints: %s"%names)

        '''
            choose first from the list, rotate the list
            write it to the actual config file TODO
        '''
        ref_endpoints = get_dict_value(['reference-endpoints'], self.config)
        self.ref_endpoint = ref_endpoints.pop(0)
        ref_endpoints.append(self.ref_endpoint)
        self.config['reference-endpoints'] = ref_endpoints
        self.config['reference-endpoint'] = self.ref_endpoint
        self.ref_end_id = get_endpoint_name(self.ref_endpoint)
        print_json_to_file(self.config_file, self.config)
        
        print_message("Using the following reference endpoint: %s"%self.ref_end_id)

        return 0

    def configure_multiprocessing(self):
        self.manager = multiprocessing.Manager()
        self.queue = multiprocessing.Queue(100)
        self.cpu_count = multiprocessing.cpu_count()
        self.report = self.manager.dict()
        self.report['failure'] = {}
        self.report['success'] = {}
        self.wait_cond = self.manager.Condition(self.manager.Lock())
        self.report['counter'] = 0

        rc = self._launch_workers()
        if (rc or len(self.workers) == 0):
            return 6
        return 0

    def do_main(self):
        print_error("abstract method needs to be overridden")
        return -1

    def do_postprocess(self):
        print_error("abstract method needs to be overridden")
        return -1

    def do_setup(self):
        print_error("abstract method needs to be overridden")
        return -1

    def do_teardown(self):
        print_error("abstract method needs to be overridden")
        return -1

    def run(self):
        rc = self.configure()
        if rc:
            return rc

        try:
            rc = self.configure_multiprocessing()
            if rc:
                self._wait_for_worker_exit()
                return rc 
        except Exception as e:
            print_error("Test suite run() failed: %s"%create_error_text(e))
            if (self.debug):
                traceback.print_exc()
            self._wait_for_worker_exit()
            return 11

        try :
            if self.do_setup():
                return 7

            if self.do_main():
                print_error("Test suite run() failed.")
        except Exception as e:
            print_error("Test suite run() failed: %s"%create_error_text(e))
            if (self.debug):
                traceback.print_exc()
        finally:
            self.do_teardown()

            self._wait_for_worker_exit()
            
            self.do_postprocess()
            return 0

    def wait_for_completion(self, end_value):
        if not self.wait_cond:
            print_error("wait_for_completion called without initializing cond object")
            return 12

        while(True):
            self.wait_cond.acquire()
            try:
                if self.debug:
                    print_message("wait_for_completion, counter %s, end_value %s"\
                                    %(self.report['counter'], end_value))
                if self.report['counter'] >= end_value:
                    break
                self.wait_cond.wait()
            finally:
                self.wait_cond.release()
        
        return 0

    def _launch_workers(self):
        print_message("Launching workers ...")
        try:
            for i in range(self.cpu_count):
                worker = Worker(i, self.queue, self.report, self.wait_cond)
                self.workers.append(worker)
                worker.start()
            return 0
        except Exception as e:
            print_error("Failed to launch workers: %s"%create_error_text(e))
            if (self.debug):
                traceback.print_exc()
            return 13

    def _wait_for_worker_exit(self):
        for i in range(self.cpu_count):
            self.queue.put(None)
            
        if (self.debug):
            print_message("Waiting for workers to exit ...")

        timeout = get_dict_value(['task-phases', 'remove', 'timeout-in-seconds'], self.config)
        map(lambda x : x.join(timeout), self.workers)

        if (self.debug):
            print_message("Workers have all exited; doing postprocess.")