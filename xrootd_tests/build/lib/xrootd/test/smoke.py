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
#  smoke.py
#
#  On the basis of a selected reference endpoint which is considered reliable,
#  a round-trip transfer is attempted between each other endpoint and that
#  reference endpoint:  a file is uploaded to the endpoint, transferred from
#  the endpoint to the reference, transferred back to the endpoint, and then
#  downloaded.   The success or failure of each phase/step is recorded.
# 
###############################################################################

import multiprocessing
import os
import traceback

from testsuite import TestSuite
from ..util.tasks import *
from ..util.reports import *
from ..util.utils import *
from distutils.spawn import find_executable

class SmokeTest(TestSuite):
    def __init__(self, debug, config_file):
        TestSuite.__init__(self, debug, config_file)
    
    def do_main(self):
        number_of_tasks = 0

        self.wait_cond.acquire()
        self.report['counter'] = 0
        self.wait_cond.release() 

        try:
            for endpoint in self.endpoints:
                t = create_roundtrip(number_of_tasks + 1, endpoint, self.config)
                number_of_tasks += 1
                self.queue.put(t)

            self.wait_for_completion(number_of_tasks)
            return 0
        except Exception as e:
            print_error("Failed to complete main test phase: %s"%create_error_text(e))
            if self.debug:
                traceback.print_exc()
            return 9

    def do_postprocess(self):
        generate_smoke_report(self.config, self.report, self.config_file)

    def do_setup(self):
        ''' 
            upload the data file to reference endpoint
            to use to test endpoint tpc as destination
            in case endpoint tpc as source fails
        '''
        local_data = get_dict_value(['local-data-file'], self.config)
        data_path = os.path.join(local_data['parent'], local_data['name'])

        self.wait_cond.acquire()
        self.report['counter'] = 0
        self.wait_cond.release()

        print_message("Attempting setup ...")

        try:
            t = create_setup(1, data_path, self.ref_endpoint, self.config)
            self.queue.put(t)

            self.wait_for_completion(1)
            return 0
        except Exception as e:
            print_error("Failed to complete setup phase: %s"%create_error_text(e))
            if self.debug:
                traceback.print_exc()
            return 8

    def do_teardown(self):
        local_data = get_dict_value(['local-data-file'], self.config)
        file_name = get_dict_value(['name'], local_data)
        data_path = os.path.join(get_dict_value(['parent'], local_data), 
                                 file_name)
        target_name = "%s-%s"%(file_name, get_dict_value(['uuid'], local_data))
        
        rc = 0
        print_message("Attempting teardown ...")

        try: 
            t = create_teardown(1, self.ref_endpoint, target_name, self.config)
            self.queue.put(t)  
        except Exception as e:
            print_error("Failed to complete teardown phase: %s"%create_error_text(e))
            if self.debug:
                traceback.print_exc()
            rc = 10
        finally:
            try:
                os.unlink(data_path)
            except:
                pass
        
        return rc 