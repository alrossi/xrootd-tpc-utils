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
#  utils.py
#
#  Routines for I/O, email, configuration validation, environment setup,
#  including proxy generation (if indicated) and data file generation
#  (if indicated), and process execution.
#
###############################################################################

import json
import multiprocessing
import os
import subprocess
import sys
import time
import smtplib
import traceback
import uuid

import tasks

from distutils.spawn import find_executable
from email.mime.text import MIMEText

debug = False

def set_global_debug(on):
    global debug
    debug = on

def is_debug():
    return debug

def get_args(config):
    args = get_dict_value(['xrootd-settings', 'debug-args'], config)
    cksm = get_dict_value(['xrootd-settings','cksum'], config)
    if not args:
        args = ""
    if not cksm:
        cksm = ""
    return "%s %s"%(args, cksm)

def get_capture(config, phase):
    return get_dict_value(['task-phases', phase, 'capture-streams'], 
                          config)

def get_timeout(config, phase):
    return get_dict_value(['task-phases', phase, 'timeout-in-seconds'], 
                          config)

def get_url(endpoint):
    return get_dict_value(['url'], endpoint)

class SrcDstUrls(object):
    def __init__(self, src, dst, config):
        self.src = src
        self.dst = dst
        self.src_id = get_endpoint_name(src)
        self.dst_id = get_endpoint_name(dst)
        self.local = get_dict_value(['local-data-file'], config)
        self.local_dir = get_dict_value(['parent'], self.local)
        self.file_name = get_dict_value(['name'], self.local)
        self.uuid = get_dict_value(['uuid'], self.local)
        self.upl_file_name = "%s-%s"%(self.file_name, self.uuid)
        self.dst_file_name = "from-%s-%s"%(self.src_id, self.uuid)
        self.ret_file_name = "from-%s-%s"%(self.dst_id, self.uuid)
        self.to_delete = [None, None, None, None]

    def __repr__(self):
        return "%s-%s-URLS"%(self.endpt_id, self.refpt_id)

    def delete_download_when_finished(self, delegate):
        self.to_delete[0] = self.get_download_path(delegate)

    def delete_upload_when_finished(self):
        self.to_delete[1] = self.get_upload_url()

    def delete_destination_when_finished(self, delegate):
        suffix = "d" if delegate else "nd"
        self.to_delete[2] = self.get_destination_url(delegate)

    def delete_return_when_finished(self, delegate):
        self.to_delete[3] = self.get_return_url(delegate)

    def get_data_path(self):
        return os.path.join(self.local_dir,self.file_name)

    def get_download_path(self, delegate):
        return self._get_suffixed(os.path.join(self.local_dir, 
                                               self.dst_file_name), 
                                  delegate)

    def get_upload_url(self):
        return os.path.join(get_url(self.src), self.upl_file_name)

    def get_destination_url(self, delegate):
        return self._get_suffixed(os.path.join(get_url(self.dst), 
                                               self.dst_file_name), 
                                  delegate)

    def get_return_url(self, delegate):
        return self._get_suffixed(os.path.join(get_url(self.src), 
                                               self.ret_file_name),
                                  delegate)

    def get_paths(self):
        return "(UPLOAD %s)(DST_D %s)(RET_D %s)(DWNLD_D %s)(DST_ND%s)(RET_ND %s)(DWNLD_ND %s)"\
            %(self.get_upload_url(),
              self. get_destination_url(True),
              self.get_return_url(True),
              self.get_download_path(True),
              self. get_destination_url(False),
              self.get_return_url(False),
              self.get_download_path(False))

    def get_to_delete(self):
        return self.to_delete

    def get_src(self):
        return self.src

    def get_dst(self):
        return self.dst

    def get_src_id(self):
        return self.src_id

    def get_dst_id(self):
        return self.dst_id

    def get_json_object(self):
        json_rep = {}
        json_rep['paths'] = self.get_paths()
        json_rep['to-delete'] = self.get_to_delete()
        return json_rep

    def is_same_endpoint(self):
        return self.dst_id == self.src_id

    def _get_suffixed(self, path, delegate):
        return "%s-%s"%(path, "D" if delegate else "ND")

class WithRefUrls(SrcDstUrls):
    def __init__(self, endpoint, config):
        SrcDstUrls.__init__(self, 
                            endpoint, 
                            get_dict_value(['reference-endpoint'], config), 
                            config) 

##  ------------------------------------------------------------------------------------
 #  I/O
##  ------------------------------------------------------------------------------------
print_lock = multiprocessing.Lock()

def create_error_text(e):
    t, v, tb = sys.exc_info()
    return "(exception: %s)(info: %s, %s, %s)"%(str(e), str(t), str(v), str(tb))

def print_error(text):
    with print_lock:
        sys.stderr.write("%s : %s\n"%(time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(time.time())),
                                                    text))
        sys.stderr.flush()

def print_message(text):
    with print_lock:
        sys.stdout.write("%s : %s\n"%(time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(time.time())),
                                                    text))
        sys.stdout.flush()

def print_message_list(list):
    with print_lock:
        for line in list:
            sys.stdout.write("%s : %s\n"%(time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(time.time())),
                                                    line))
        sys.stdout.flush()

def print_lines_to_file(path, lines):
    try:  
        with open(path, 'w') as outfile:
            for line in lines:
                outfile.write("%s\n"%line)
            outfile.flush()
        print_message("file ready at %s"%path)
    except Exception as e:
        print_error("print lines to file failure: %s"%create_error_text(e))

##  ------------------------------------------------------------------------------------
 #  JSON
##  ------------------------------------------------------------------------------------

##
#  Recursively convert object to json, calling 'get_json_object' on Tasks.
##
def get_json_object(obj):
    if (isinstance(obj, list)):
        return list(map(lambda x: get_json_object(x), list))

    if (isinstance(obj, dict)): 
        json_dict = {}
        for key in obj.keys():
            json_dict[key] = get_json_object(get_dict_value([key], obj))
        return json_dict

    if (isinstance(obj, tasks.Task)):
        return obj.get_json_object()
    
    return obj

def load_json_configuration(path):
    try:
        with open(path) as json_file:  
            return json.load(json_file)
    except Exception as e:
        print_error("Failed to load configuration: %s"%create_error_text(e))
        if (debug):
            traceback.print_exc()
        return None

def print_json_to_file(path, json_object):
    try:  
        with open(path, 'w') as outfile:  
            json.dump(json_object, outfile, indent=4, sort_keys=True)
        print_message("json file ready at %s"%path)
    except Exception as e:
        print_error("print json failure: %s"%create_error_text(e))

##  ------------------------------------------------------------------------------------
 #  Email
##  ------------------------------------------------------------------------------------
def send_email(textfile, subject, from_addr, to_list, smtp_host):
        with open(textfile, 'rb') as infile:
                # Create a text/plain message
                msg = MIMEText(infile.read())

        c_delim_to = ""
        for t in to_list:
                if len(c_delim_to) > 0:
                        c_delim_to = "%s,"%c_delim_to
                c_delim_to = "%s%s"%(c_delim_to, t.encode('ascii', 'ignore'))

        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = c_delim_to

        # Send the message via our own SMTP server, but don't include the
        # envelope header.
        s = smtplib.SMTP(smtp_host)
        s.sendmail(from_addr, to_list, msg.as_string())
        s.quit()

##  ------------------------------------------------------------------------------------
 #  Validation and Configuration
##  ------------------------------------------------------------------------------------
def get_dict_value(keys, dictionary):
    if not dictionary:
        msg = "No dictionary value, failed to retrieve %s: "%keys
        raise Exception(msg)

    d = dictionary
    v = None
    for k in keys:
        v = d.get(k, None)
        if not v:
            return None
        d = v
    return v

def get_version(xrd_cp):
    p = subprocess.Popen("%s --version"%xrd_cp,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    if not p:
        return "no descriptor for %s"%command

    try:
        stdout, stderr = p.communicate()
        lines = stderr.split('\n')
        print_message("XrootD client version: %s"%lines[0])
        return lines[0]
    except Exception, e:
        return "could not get version: %s"%str(e)

def validate_configuration(config):
    xrd_home = get_dict_value(['xrootd-settings', 'home'], config)

    if not xrd_home:
        config['xrootd-settings']['xrdcp'] = 'xrdcp'
        config['xrootd-settings']['xrdfs'] = 'xrdfs'
    else:
        if not (os.path.isfile("%s/bin/xrdcp"%xrd_home)):
            print_error("could not find executable %s/bin/xrdcp"%xrd_home)
            return 12
        config['xrootd-settings']['xrdcp'] = "%s/bin/xrdcp"%xrd_home

        if not (os.path.isfile("%s/bin/xrdfs"%xrd_home)):
            print_error("could not find executable %s/bin/xrdfs"%xrd_home)
            return 13
        config['xrootd-settings']['xrdfs'] = "%s/bin/xrdfs"%xrd_home

    data_gen_exec = get_dict_value(['local-data-file', 'generator-exec'], config)
    if data_gen_exec and not (find_executable(data_gen_exec)):
        print_error("could not find executable %s/"%data_gen_exec)
        return 14

    return 0

def validate_proxy(gsi_settings):
    if get_dict_value(["generate-proxy"], gsi_settings):
        proxy_exec = get_dict_value(["proxy-init-exec"], gsi_settings)
        
        if not proxy_exec or not (find_executable(proxy_exec)):
            print_error("could not find proxy init executable (%s)"%proxy_exec)
            return 15

        rc = execute_command("%s %s"%(proxy_exec, 
                                      get_dict_value(["proxy-init-args"], gsi_settings)))
        if rc :
            print_error("Failed to create proxy")
            return 16

    proxy = get_dict_value(["x509-user-proxy"], gsi_settings)

    if not (os.path.isfile(proxy)):
        print_error("No user proxy found at '%s'"%proxy)
        return 17

    proxy_info = get_dict_value(['proxy-info-exec'], gsi_settings)
        
    if not proxy_info:
        print_message("proxy info executable undefined, skipping proxy verification")
        return 0
        
    '''
        We skip verifying this as executable path as it probably is installed and
        available to the shell on the $PATH.
           
        It is assumed this will be either grid-proxy-init or voms-proxy-init;
        this also means we rely on the output to give us a line with 'timeleft:'.
    '''
    cmd = "%s %s -file %s"%(proxy_info, get_dict_value(["proxy-info-args"], gsi_settings), proxy)

    p = subprocess.Popen(cmd, 
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    output, errors = p.communicate()
      
    if p.returncode:
        print_error("Command \"%s\" failed: rc=%d, error=%s"%(cmd,
                                                              p.returncode, 
                                                              errors.replace('\n',' ')))
        return 19

    '''
        parse output for last timeleft line, e.g. "timeleft  : 12:23:43"
    ''' 
    timeleft = ""
    lines = output.split('\n')
    for line in lines:
        if "timeleft" in line:
            timeleft = line

    colons = timeleft.split(':')
    if len(colons) != 4:
        print_error("error parsing timeleft on proxy: %s"%timeleft)
        return 20

    secs = 0
    d = 3600
    for i in range(1, 4):
        secs += d * int(colons[i])
        d = d/60

    if secs < 300:
        print_error("insufficient time left on proxy: %s seconds"%secs)
        return 21

    return 0

##  ------------------------------------------------------------------------------------
 #  Setup
##  ------------------------------------------------------------------------------------
def generate_data_file(config):
    data_file = get_dict_value(['local-data-file'], config)
    data_file_name = get_dict_value(['name'], data_file)
    path = os.path.join(get_dict_value(['parent'], data_file),
                        data_file_name)

    '''
        create a uuid for this test instance
    '''
    data_file['uuid'] = "%s"%str(uuid.uuid4())

    if (not os.path.isfile(path) and get_dict_value(['generate'], data_file)):
        rc = execute_command("%s %s"%(get_dict_value(["generator-exec"], data_file), 
                                      get_dict_value(["generator-args"], data_file)))
        if rc :
            print_error("Failed to generate data file")
            return rc
        elif not os.path.isfile(path):
            return 18
    return 0

def generate_permuted_pairs(endpoints):
    p = []
    n = len(endpoints)
    i = 0
    while i < n-1:
        j = i+1
        while j < n:
            p.append((endpoints[i], endpoints[j]))
            p.append((endpoints[j], endpoints[i]))
            j += 1
        i += 1
    return p

def get_endpoint_name(endpoint):
    return endpoint['id'].encode('ascii', 'ignore')

def get_endpoint_names(endpoints):
    return list(map(lambda x : get_endpoint_name(x), endpoints))

def get_endpoint_pair_names(pairs):
    names = []
    for (src, dst) in pairs:
        names.append((get_endpoint_name(src), 
                      get_endpoint_name(dst)))
    return names

def prepare_environment(config):
    gsi_settings    = get_dict_value(['gsi-settings'], config)
    xrootd_settings = get_dict_value(['xrootd-settings'], config)

    try:
        os.environ["X509_USER_KEY"]     = gsi_settings['x509-user-key']
        os.environ["X509_USER_CERT"]    = gsi_settings['x509-user-cert']
        os.environ["X509_CERT_DIR"]     = gsi_settings['x509-cert-dir']
        os.environ["X509_USER_PROXY"]   = gsi_settings['x509-user-proxy']

        rc = validate_proxy(gsi_settings)
        if rc:
            return rc

        home = get_dict_value(['home'], xrootd_settings)
        lib = get_dict_value(['lib'], xrootd_settings)
        
        if not (os.environ.has_key("LD_LIBRARY_PATH")):
            os.environ["LD_LIBRARY_PATH"]   = "%s/%s:"%(home, lib)
        else:
            os.environ["LD_LIBRARY_PATH"]   = "%s/%s:%s"%(home, lib, 
                                                          os.environ["LD_LIBRARY_PATH"])

        return 0
    except Exception as e:
        print_error("Failed to set os environment: %s"%create_error_text(e))
        if (debug):
            traceback.print_exc()
        return 22

##  ------------------------------------------------------------------------------------
 #  Exec
##  ------------------------------------------------------------------------------------
def execute_command(cmd):
    p = subprocess.Popen(cmd, 
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    output, errors = p.communicate()
    rc = p.returncode

    '''
        consider no return value a success
    '''
    if not rc:
        rc = 0

    if rc:
        with print_lock:
            print_error("Command \"%s\" failed: rc=%d, error=%s"%(cmd,
                                                                  rc, 
                                                                  errors.replace('\n',' ')))
    return rc
