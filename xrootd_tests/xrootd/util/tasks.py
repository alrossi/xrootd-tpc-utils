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
#  tests.py
#
#  Class definitions for the various kinds of tests, plus create methods.
#
#  These include:  XrdUploadFile, XrdDownloadFile, XrdRemoveFile, 
#                  XrdThirdPartyTransfer, XrdRoundTrip
#
#                  The latter is composed of:
#  
#                       XrdUploadFile to A
#                       XrdThirdPartyTransfer from A to B, 
#                       XrdThirdPartyTransfer from B to A,
#                       XrdDownloadFile from A
#                       XrdRemoveFile from A
#
#  The write, tpc and remove tasks are used independently in the full mesh
#                  test suite, while the roundtrip is used by the smoke
#                  test suite.
###############################################################################

import signal
import subprocess
import threading
import os
import traceback
import uuid
import errno

from utils import *
from urlparse import urlsplit

def signal_handler(signum, frame):
    raise Exception("TIMEDOUT")

class Task(object):
    def __init__(self, id, config):
        self.id = id
        self.log_file_name = id
        self.config = config
        self.xrd_home = get_dict_value(['xrootd-settings', 'home'], config)
        self.xrd_cp = get_dict_value(['xrootd-settings', 'xrdcp'], config)
        self.xrd_fs = get_dict_value(['xrootd-settings', 'xrdfs'], config)
        self.errors = []
        self.capture_streams = False
        self.timestamp = get_dict_value(['run-timestamp'], config)

    def __repr__(self):
        return self.id

    def get_json_object(self):
        return {'id': self.id, 'xrd_home': self.xrd_home, 
                'errors': self.errors, 'log_file_name': self.log_file_name}

    def run(self):
        rc = 0

        try:
            self._print_env()
            rc = self._do_task()
        except Exception, e:
            rc = 1
            self.errors.append("subprocess _do_task: %s"%str(e))
            if is_debug():
                traceback.print_exc()
            pass
        
        return rc

    def _clean_up(self, timeout, remote, local):
        for url in remote:
            if not url:
                continue
           
            scheme, loc, path, query, frag = urlsplit(url)
            command = "%s %s rm %s"%(self.xrd_fs, loc, path)
            
            rc = self._do_timedTask(command, timeout, "clean-up on %s"%url)
            if rc:
                print_error("failed to remove %s. rc: %s"%(url, rc))

        for path in local:
            if not path:
                continue
            try:
                if os.path.exists(path):
                    print_message("removing local %s"%(path))
                    os.unlink(path)
            except Exception, e:
                print_error("failed to remove local %s: %s"%(path, create_error_text(e)))
        self.to_unlink = []

    def _do_task(self):
        return self._do_timedTask(None, 0, "no task has been defined")

    def _do_timedTask(self, command, timeout, description):
        if not command:
            return 1

        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(timeout)
        
        print_message("running %s"%description)
        if is_debug():
            print_message("%s"%command)

        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        if not p:
            if is_debug():
                print_error("subprocess_open returned no process descriptor for %s"%command)
            self.errors.append("subprocess_open returned no process descriptor for %s"%command)
            return 1

        timer = threading.Timer(timeout, self._kill_process, [p])

        try:
            timer.start()
            stdout, stderr = p.communicate()
            if stdout:
                self._process_lines(stdout, "OUT")  
            if stderr:
                self._process_lines(stderr, "ERR")
        finally:
            timer.cancel()
            signal.alarm(0)

            rc = p.returncode

            '''
                if the process is killed there may not be
                an exit code
            '''
            if not rc and rc != 0:
                rc = -1

            if rc:
                print_message("%s failed"%description)
            else:
                print_message("%s succeeded"%description)

            return rc
    
    def _get_remove_command(self, url, file_name):
        scheme, loc, path, query, frag = urlsplit(url)
        return "%s %s rm %s"%(self.xrd_fs, loc, 
                              os.path.join(path, file_name))

    def _kill_process(self, p):
        p.kill()
        if is_debug():
            print_error("subprocess_kill: TIMEDOUT")
        self.errors.append('subprocess_kill: TIMEDOUT')
    
    def _print_env(self):
        if self.capture_streams:
            p = subprocess.Popen("env",
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 shell=True)
            if not p:
                if is_debug():
                    print_error('_print_env returned no process descriptor for env')
                self.errors.append('_print_env returned no process descriptor for env')
                return -1

            try:
                stdout, stderr = p.communicate()
                if stdout:
                    self._process_lines(stdout, "ENV")  
            finally:
                return p.returncode
        
            return 0
    
    def _process_lines(self, message, stream):
        lines = message.split('\n')
        index = 0
        log = None

        if self.capture_streams:
            dir = get_dict_value(['report', 'log-dir'], self.config)
            path = os.path.join(dir, "%s-%s.log"%(self.log_file_name, 
                                                  self.timestamp))

            try:
                try:
                    os.makedirs(dir)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
                log = open(path, 'a')
            except Exception as e:
                print_error("_process_lines: %s"%create_error_text(e))

        for line in lines:
            padded = str(index).zfill(6)
            if ("[Error" in line or "[ERROR]" in line):
                self.errors.append("%s : %s"%(padded, line))
            if log:
                try:
                    log.write("%s-%s: %s\n"%(stream, padded, line))
                except Exception as e:
                    pass
            index += 1

        if log:
            try:
                log.flush()
            except Exception as e:
                    pass
            finally:
                log.close()

class XrdUploadFile(Task):
    def __init__(self, id, urls, config):
        Task.__init__(self, id, config)
        self.urls = urls
        self.endpoint = urls.get_src()
        self.log_file_name = "%s-upload"%urls.get_src_id()
        self.args = get_args(config)
        self.capture_streams = get_capture(config, 'upload')
    
    def get_json_object(self):
        json_rep = super(XrdUploadFile, self).get_json_object()
        json_rep['endpoint'] = self.urls.get_src()
        json_rep['upload-url'] = self.urls.get_upload_url()
        json_rep['args'] = self.args
        return json_rep

    def _do_task(self):
        timeout = get_timeout(self.config, 'upload')
        command = self._get_copy_command()
        description = "data upload to %s"%self.urls.get_src_id()
        return self._do_timedTask(command, timeout, description)

    def _get_copy_command(self):
        return "%s %s %s %s"%(self.xrd_cp, 
                              self.args, 
                              self.urls.get_data_path(),
                              self.urls.get_upload_url())

class XrdDownloadFile(Task):
    def __init__(self, id, urls, ret, delegate, config):   
        Task.__init__(self, id, config)
        self.urls = urls
        self.endpoint = urls.get_src()
        self.source_url = urls.get_return_url(delegate)\
            if ret else urls.get_upload_url()
        self.delegate = delegate
        self.log_file_name = "%s-download"%urls.get_src_id()
        self.args = get_args(config)
        self.capture_streams = get_capture(config, 'download')
    
    def get_json_object(self):
        json_rep = super(XrdDownloadFile, self).get_json_object()
        json_rep['endpoint'] = self.urls.get_src()
        json_rep['source-url'] = self.source_url
        json_rep['download-path'] = self.urls.get_download_path(self.delegate)
        json_rep['delegate'] = self.delegate
        json_rep['args'] = self.args
        return json_rep

    def _do_task(self):
        timeout = get_timeout(self.config, 'download')
        command = self._get_copy_command()
        description = "data download from %s"%self.urls.get_src_id()
        return self._do_timedTask(command, timeout, description)

    def _get_copy_command(self):
        return "%s %s %s %s"%(self.xrd_cp, 
                              self.args, 
                              self.source_url,
                              self.urls.get_download_path(self.delegate))

class XrdThirdPartyTransfer(Task):
    def __init__(self, id, 
                 src, src_id, src_url, 
                 dst, dst_id, dst_url, 
                 delegate, cleanup, config):
        Task.__init__(self, id, config)
        self.src = src
        self.src_id = src_id
        self.src_url = src_url
        self.dst = dst
        self.dst_id = dst_id
        self.dst_url = dst_url
        self.args = get_args(config)
        self.delegate = delegate
        self.log_file_name = "%s-to-%s-%s"%(self.src_id, 
                                            self.dst_id, 
                                            "d" if delegate else "nd")
        self.capture_streams = get_capture(config, 'tpc')
        self.cleanup = cleanup

    def get_json_object(self):
        json_rep = super(XrdThirdPartyTransfer, self).get_json_object()
        json_rep['src'] = self.src
        json_rep['dst'] = self.dst
        json_rep['src_url'] = self.src_url
        json_rep['dst_url'] = self.dst_url
        json_rep['args'] = self.args
        json_rep['delegate'] = self.delegate
        json_rep['capture-streams'] = self.capture_streams
        return json_rep

    def _do_task(self):
        timeout = get_timeout(self.config, 'tpc')
        with_delegation = "with" if self.delegate else "without"
        description = "third-party transfer %s delegate from %s to %s"
        rc = self._do_timedTask(self._get_copy_command(), 
                                timeout, 
                                description%(with_delegation, 
                                            self.src_id, 
                                            self.dst_id))

        if self.cleanup or rc:
            '''
                Try to clean up if indicated or on failure.
            '''
            self._clean_up(timeout, [self.dst_url], [])

        return rc
    
    def _get_copy_command(self):
        tpc = ""

        if self.delegate:
            tpc = "--tpc delegate only"
        else:
            tpc = "--tpc only"

        return "%s %s %s %s %s"%(self.xrd_cp, 
                                 self.args,
                                 tpc, 
                                 self.src_url, 
                                 self.dst_url)

class XrdRemoveFile(Task):
    def __init__(self, id, endpoint, file, config):
        Task.__init__(self, id, config)
        self.endpoint = endpoint
        self.log_file_name = "%s-remove"%get_endpoint_name(self.endpoint)
        self.file_name = file
        self.capture_streams = get_capture(config, 'remove')

    def get_json_object(self):
        json_rep = super(XrdRemoveFile, self).get_json_object()
        json_rep['endpoint'] = self.endpoint
        json_rep['file_name'] = self.file_name
        return json_rep
    
    def _do_task(self):
        timeout = get_timeout(self.config, 'remove')
        description = "data removal from %s"%get_endpoint_name(self.endpoint)
        return self._do_timedTask(self._get_remove_command(get_url(self.endpoint), 
                                                           self.file_name), 
                                 timeout,
                                 description)

class XrdRoundTrip(Task):
    def __init__(self, id, endpoint, config):
        Task.__init__(self, id, config)
        self.endpoint = endpoint
        self.log_file_name = "%s-round-trip"%get_endpoint_name(self.endpoint)
        self.urls = WithRefUrls(endpoint, config)
        self.tpc = get_dict_value(['task-phases', 'tpc'], config)
        self.with_deleg = get_dict_value(['with-delegation'], self.tpc)
        self.tasks = []
        self.results = [-999, -999, -999, -999, -999, -999]
        self.is_ref = self.urls.is_same_endpoint()
        if is_debug():
            print_message("URLS: %s"%self.urls.get_paths())
    
    def get_json_object(self):
        json_rep = super(XrdRoundTrip, self).get_json_object()
        json_rep['endpt_id'] = self.urls.src_id
        json_rep['urls'] = self.urls.get_json_object()
        json_rep['tasks'] = []
        for t in self.tasks:
            json_rep['tasks'].append(t.get_json_object())
        json_rep['results'] = self.results
        return json_rep

    def is_sound(self, valid):
        for i in valid:
            rc = self.results[i]
            if rc:
                return False
        return True
    
    def _do_download(self, ret, delegate):
        '''
            Attempt to read the file from the endpoint.
            This will obviously fail if the file never got there or
            is corrupt.
        '''
        task = XrdDownloadFile("%s-%s"%(self.id, "download"),
                               self.urls,
                               ret,
                               delegate,
                               self.config)
        self.tasks.append(task)
        '''
           remove copy from local directory
        '''
        self.urls.delete_download_when_finished(delegate)
        print_message("DOWNLOAD from %s"%self.urls.get_src_id())
        rc = task.run()
        if rc:
            print_error("DOWNLOAD from %s failed"%self.urls.get_src_id())
        return rc

    def _do_task(self):
        valid_rcs = []
        timeout = get_timeout(self.config, 'tpc')

        ## upload
        if not self.is_ref:
            self.results[0]= self._do_upload()
            valid_rcs.append(0)

        ## bidirectional
        if self.with_deleg:
            self._do_bi_directional(True, valid_rcs)
            '''
                If the return copy was successful, use it as source;
                otherwise, try download with the uploaded file.
            '''
            ## download
            self.results[5] = self._do_download(self.results[3] == 0, True)
            valid_rcs.append(5)
            ## remove destination files and local
            to_delete = self.urls.get_to_delete()
            self._clean_up(timeout, 
                           [to_delete[2], to_delete[3]], 
                           [to_delete[0]])
        
        else:
            self._do_bi_directional(False, valid_rcs)
            '''
                If the return copy was successful, use it as source;
                otherwise, try download with the uploaded file.
            '''
            ## download
            self.results[5] = self._do_download(self.results[4] == 0, False)
            valid_rcs.append(5)
            ## remove destination files and local
            to_delete = self.urls.get_to_delete()
            self._clean_up(timeout, 
                           [to_delete[2], to_delete[3]], 
                           [to_delete[0]])

        ## remove upload file
        upload_url = self.urls.get_to_delete()[1]
        self._clean_up(timeout, [upload_url], [])

        return 0 if self.is_sound(valid_rcs) else 1

    def _do_bi_directional(self, delegate, valid_rcs):
        ## tpc src
        ## the reference endpoint should already have the source file
        if self.results[0] == 0 or self.is_ref:
            if delegate:
                self.results[1] = self._do_tpc_src(True, False)
                valid_rcs.append(1)
            else:
                self.results[2] = self._do_tpc_src(False, False)
                valid_rcs.append(2)
        else:  
            print_error("skipping tpc using %s as source"%self.endpt_id)

        ## tpc dst
        '''
            Testing src on the reference endpoint is sufficient,
            because it is already also acting as dst
        '''
        if not self.is_ref:
            ''' 
                Use the dst file as source.
            '''
            if delegate and self.results[1] == 0:
                self.results[3] = self._do_tpc_dst(True, True, False)
                valid_rcs.append(3)
            elif not delegate and self.results[2] == 0:
                self.results[4] = self._do_tpc_dst(True, False, False)
                valid_rcs.append(4)
            else:
                '''
                    The source target on the destination (reference endpoint)
                    will have been preloaded and can be used to test
                    the second tpc (endpoint as dst).
                '''
                if delegate:
                    self.results[3] = self._do_tpc_dst(False, True, False)
                    valid_rcs.append(3)
                else:
                    self.results[4] = self._do_tpc_dst(False, False, False)
                    valid_rcs.append(4)

    def _do_tpc_dst(self, dst, delegate, cleanup):
        '''
            Transfer uploaded file (in case of failure of the previous
            transfer, dst = False) or the destination file from 
            reference endpoint back to the selected endpoint.
        '''
        deleg = "d" if delegate else "nd"
        source_url = self.urls.get_destination_url(delegate)\
            if dst else self.urls.get_upload_url()
        if is_debug():
            print_message("RETURN TPC, using %s as source"%source_url)
        task = XrdThirdPartyTransfer("%s-%s-%s"%(self.id, "tpc-dst", deleg), 
                                     self.urls.get_dst(),
                                     self.urls.get_dst_id(),
                                     source_url,
                                     self.urls.get_src(),
                                     self.urls.get_src_id(),
                                     self.urls.get_return_url(delegate),
                                     delegate,
                                     cleanup,
                                     self.config)
        self.tasks.append(task)
        '''
            remove the return copy from endpoint
        '''
        self.urls.delete_return_when_finished(delegate)
        
        print_message("TPC from %s to %s (%s)"%(self.urls.get_dst_id(), 
                                                self.urls.get_src_id(),
                                                deleg))
        rc = task.run()
        if rc:
            print_error("TPC from %s to %s (%s) FAILED"%(self.urls.get_dst_id(), 
                                                         self.urls.get_src_id(),
                                                         deleg)) 
        return rc

    def _do_tpc_src(self, delegate, cleanup):
        '''
            Transfer uploaded file to reference endpoint. 
        '''
        deleg = "d" if delegate else "nd"
        task = XrdThirdPartyTransfer("%s-%s-%s"%(self.id, "tpc-src", deleg),
                                     self.urls.get_src(),
                                     self.urls.get_src_id(),
                                     self.urls.get_upload_url(),
                                     self.urls.get_dst(),
                                     self.urls.get_dst_id(),
                                     self.urls.get_destination_url(delegate),
                                     delegate,
                                     cleanup,
                                     self.config)
        self.tasks.append(task)
        '''
            remove destination file from ref endpoint
        '''
        self.urls.delete_destination_when_finished(delegate)

        print_message("TPC from %s to %s (%s)"%(self.urls.get_src_id(), 
                                                self.urls.get_dst_id(),
                                                deleg))
        rc = task.run()
        if rc:
            print_error("TPC from %s to %s (%s) FAILED"%(self.urls.get_src_id(), 
                                                         self.urls.get_dst_id(),
                                                         deleg)) 
        return rc

    def _do_upload(self):
        '''
            Upload target to endpoint; if it fails, cleanup and exit.
        '''
        task = XrdUploadFile("%s-%s"%(self.id, "upload"), 
                             self.urls,
                             self.config)
        self.tasks.append(task)
        '''
            remove uploaded file from endpoint
        '''
        self.urls.delete_upload_when_finished()
        print_message("UPLOAD to %s"%self.urls.get_src_id())
        rc = task.run()
        if rc:
             print_error("UPLOAD to %s failed"%self.urls.get_src_id())
        
        return rc

def create_setup(testno, data_path, endpoint, config):
    urls = WithRefUrls(endpoint, config)
    return XrdUploadFile("%s-%s"%('set-up', testno), 
                         urls,
                         config)

def create_tpc_test(testno, src, dst, delegate, config):
    urls = SrcDstUrls(src, dst, config)
    deleg = "d" if delegate else "nd"
    return XrdThirdPartyTransfer("%s-%s-%s"%('tpc-test', deleg, testno),
                                 urls.get_src(),
                                 urls.get_src_id(),
                                 urls.get_upload_url(),
                                 urls.get_dst(),
                                 urls.get_dst_id(),
                                 urls.get_destination_url(delegate),
                                 delegate,
                                 True,
                                 config)

def create_teardown(testno, endpoint, file, config):
    return XrdRemoveFile("%s-%s"%('tear-down', testno), endpoint, file, config)

def create_roundtrip(testno, endpoint, config):
    return XrdRoundTrip("%s-%s"%('round-trip', testno), endpoint, config)
