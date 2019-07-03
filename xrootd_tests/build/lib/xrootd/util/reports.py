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
#  reports.py
#
#  Routines which handle the post-processing of test output.
#
#  Compiles the raw data into a statistical summary report which also
#  lists the last error line associated with each failure.
#
###############################################################################

import os
import socket

from string import *
from time import strftime,gmtime
from utils import *
from tasks import Task

'''
CERN-TRUNK      DPM
        success 6, failure 0, (100.00%),                
        as src: success 3, failure 0, (100.00%),                
        as dst: success 3, failure 0, (100.00%)
'''

SMOKE_FORMAT='{0:<8}{1:<20}{2:<10}{3:^7}{4:^7}{5:^7}{6:^7}{7:^7}{8:^7}{9:^10}'
MESH_FORMAT='{0:<25}{1:<10} tests run: {2:^10}\n{3:>25}:  success{4:^5} failure{5:^5} ({6:>7})\n{7:>25}:  success{8:^5} failure{9:^5} ({10:>7})\n{11:>25}:  success{12:^5} failure{13:^5} ({14:>7})\n'

def compare_endpoints_by_score(summary1, summary2):
    if not isinstance(summary1, SmokeSummary):
        return compare_endpoints_by_rank(summary1, summary2)

    score1 = summary1.score
    score2 = summary2.score

    cp = score2 - score1
    if cp == 0:
        return compare_endpoints_by_rank(summary1, summary2)

    return cp

def compare_endpoints_by_rank(summary1, summary2):
    rank1 = summary1.get_ranking()
    rank2 = summary2.get_ranking()

    if rank1 < rank2:
        return 1
    elif rank1 > rank2:
        return -1

    name1 = summary1.name
    name2 = summary2.name 

    if name1 < name2:
        return -1
    if name1 > name2:
        return 1
    return 0

def get_summary_path(config, summary, ext):
    return os.path.join(get_dict_value(['report', 'output-dir'], config),
                        "%s.%s"%(get_dict_value(['report', summary], config), ext))

class SuccessStatistics(object):
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failure = 0

    def increment(self):
        self.total +=1
        self.success +=1

    def increment_failed(self):
        self.total +=1
        self.failure +=1

class FullMeshSummary(object):
    def __init__(self, id, endpoint):
        self.name = id
        self.endpoint = endpoint
        self.setup_succeeded = False
        self.last_error = ""
        self.teardown_succeeded = False
        self.as_destination = SuccessStatistics()
        self.as_source = SuccessStatistics()
        self.failed_as_dst = []
        self.failed_as_src = []

    def add_test_failure(self, role, remote, tid, last):
        if 'src' in role:
            self.as_source.increment_failed()
            message = "with dst %s (%s)"%(remote, tid)
            self.failed_as_src.append("%s, last error was: %s"%(message, last))
        elif 'dst' in role:
            self.as_destination.increment_failed()
            message = "with src %s (%s)"%(remote, tid)
            self.failed_as_dst.append("%s, last error was: %s"%(message, last))
        
    def add_test_success(self, role):
        if 'src' in role:
            self.as_source.increment()
        elif 'dst' in role:
            self.as_destination.increment()

    def get_ranking(self):
        total = self.as_source.total + self.as_destination.total
        success = self.as_source.success + self.as_destination.success
        return 0 if total == 0 else success*100.00/total

    def has_failures(self):
        return len(self.failed_as_dst) > 0 or len(self.failed_as_src) > 0

    def stats(self, total):
        actual = self.as_source.total + self.as_destination.total
        if total > actual:
            total = actual
        out = []
        out.append("%s/%s"%(actual, total))
        out.append("total")
        success = self.as_source.success + self.as_destination.success
        failure = self.as_source.failure + self.as_destination.failure
        as_src_percent = 0 if self.as_source.total == 0 else self.as_source.success*100/self.as_source.total
        as_dst_percent = 0 if self.as_destination.total == 0 else self.as_destination.success*100/self.as_destination.total
        out.append(success)
        out.append(failure)
        out.append("%.2f%%"%self.get_ranking())
        out.append("as src")
        out.append(self.as_source.success)
        out.append(self.as_source.failure)
        out.append("%.2f%%"%as_src_percent)
        out.append("as dst")
        out.append(self.as_destination.success)
        out.append(self.as_destination.failure)
        out.append("%.2f%%"%as_dst_percent)
        return out
    
    def update(self, role, job):
        last = len(job['task']['errors'])-1
        if last >= 0:
            self.last_error = job['task']['errors'][last]

        if not job['rc']:
            if 'set-up' in role:
                self.setup_succeeded = True
            elif 'tear-down' in role:
                self.teardown_succeeded = True
            else:
                self.add_test_success(role)
        elif 'src' in role:
            dst = job['task']['dst']['id']
            tid = job['task']['id']
            self.add_test_failure(role, dst, tid, self.last_error)
        elif 'dst' in role:
            src = job['task']['src']['id']
            tid = job['task']['id']
            self.add_test_failure(role, src, tid, self.last_error)

class SmokeSummary(object):
    def __init__(self, id, with_deleg, without_deleg, is_ref):
        self.name = id
        self.rc = []
        self.upload = "UNDF"
        self.tpc_src_d = "UNDF"
        self.tpc_src_nd = "UNDF"
        self.tpc_dst_d = "UNDF"
        self.tpc_dst_nd = "UNDF"
        self.download = "UNDF"
        self.with_deleg = with_deleg
        self.without_deleg = without_deleg
        self.is_ref = is_ref
        self.score = 0
        self.errors = []

    def get_ranking(self):
        total = len(self.rc)
        return 0 if total == 0 else self.get_successes()*100.00/total

    def get_successes(self):
        success = 0
        for n in self.rc:
            if n == 0:
                success += 1
        return success
    
    def has_failures(self):
        for n in self.rc:
            if n:
                return True
        return False

    def stats(self):
        out = []
        out.append('-' if self.is_ref else self.upload)
        out.append('-' if not self.with_deleg else self.tpc_src_d)
        out.append('-' if not self.without_deleg else self.tpc_src_nd)
        out.append('-' if not self.with_deleg else self.tpc_dst_d)
        out.append('-' if not self.without_deleg else self.tpc_dst_nd)
        out.append(self.download)
        out.append('%s/%s'%(self.get_successes(), len(self.rc)))
        return out
    
    def update(self, task):
        self.rc = task['results']
        self.upload = self._status(0)
        self.tpc_src_d = self._status(1)
        self.tpc_src_nd = self._status(2)
        self.tpc_dst_d = self._status(3)
        self.tpc_dst_nd = self._status(4)
        self.download = self._status(5)

        if self.is_ref or not self.without_deleg:
            del self.rc[4]

        if self.is_ref or not self.with_deleg:
            del self.rc[3]

        if not self.without_deleg:         
            del self.rc[2]

        if not self.with_deleg:
            del self.rc[1]
 
        if self.is_ref:
            del self.rc[0]
            
        tasks = task['tasks']
        for subtask in tasks:
            id = subtask['id']
            if 'upload' in id and self.upload == 'F':
                self._append_last_error('UPLOAD', subtask)
            elif 'tpc-src-d' in id and self.tpc_src_d == 'F':
                self._append_last_error('TPC_SRC_D', subtask)
            elif 'tpc-src-nd' in id and self.tpc_src_nd == 'F':
                self._append_last_error('TPC_SRC_ND', subtask)
            elif 'tpc-dst-d' in id and self.tpc_dst_d == 'F':
                self._append_last_error('TPC_DST_D', subtask)
            elif 'tpc-dst-nd' in id and self.tpc_dst_nd == 'F':
                self._append_last_error('TPC_DST_ND', subtask)
            elif 'download' in id and self.download == 'F':
                self._append_last_error('DOWNLOAD', subtask)

    def update_score(self, current_score):
        if self.has_failures():
            self.score = max([0, current_score - 1])
        else:
            self.score = min([20, current_score + 1])

    def _append_last_error(self, phase, subtask):
        last_err = len(subtask['errors'])-1
        if last_err >= 0:
            error = subtask['errors'][last_err]
            self.errors.append("%s (%s): %s"%(phase, subtask['id'], error))
    
    def _status(self, i):
        if self.rc[i] == 0:
            return "P"
        elif self.rc[i] == -999:
            return "-"
        else:
            return "F"

class Report(object):
    def __init__(self, config, config_file):
        self.config = config
        self.config_file = config_file
        self.raw_json = {}
        self.summary_lines = []
        self.endpoints = {}
        self.endpointmap = {}
        self.timestamp = "%s"%strftime("%Y-%m-%d %H:%M:%S GMT", gmtime())

    def create_json_output(self, report, name):
        report_local = report.copy()
        self.raw_json['config'] = self.config
        endpoints = get_dict_value(['endpoints'], self.config)
        for e in endpoints:
            self.endpointmap[e['id']] = (e['type'], e['score'])
        self.raw_json['tests'] = get_json_object(report_local)
        path = get_summary_path(self.config, name, 'json')
        print_json_to_file(path, self.raw_json)

    def create_smoke_summary(self):
        successes = get_dict_value(['tests', 'success'], self.raw_json)
        failures = get_dict_value(['tests', 'failure'], self.raw_json)
        d = get_dict_value(['task-phases', 'tpc', 'with-delegation'], self.config)
        nd = get_dict_value(['task-phases', 'tpc', 'without-delegation'], self.config)
        num_tests = 0

        if successes:
            for name in successes:
                if 'round-trip' in name:
                    task = get_dict_value([name, 'task'], successes)
                    id = get_dict_value(['endpt_id'], task)
                    self._update_smoke(id, task, d, nd)
                    num_tests +=1

        if failures:
            for name in failures:
                if 'round-trip' in name:
                    task = get_dict_value([name, 'task'], failures)
                    id = get_dict_value(['endpt_id'], task)
                    self._update_smoke(id, task, d, nd)
                    num_tests +=1

        '''
            update scores (before sorting)
        '''
        for summary in self.endpoints.values():
            (typ, oldscore) = get_dict_value([summary.name], self.endpointmap)
            summary.update_score(oldscore)
            self.endpointmap[summary.name] = (typ, summary.score)

        self._update_scores(self.config_file)

        sorted_summaries = sorted(self.endpoints.values(), cmp=compare_endpoints_by_score)
        sound = []
        problematic = []

        for summary in sorted_summaries:
            if summary.has_failures():
                problematic.append(summary)
            else:
                sound.append(summary)
                           
        self.summary_lines = self._create_smoke_summary_output(num_tests, sound, problematic)
        path = get_summary_path(self.config, 'smoke-summary-name', 'txt')
        print_lines_to_file(path, self.summary_lines)
        return path

    def create_full_mesh_summary(self):
        successes = get_dict_value(['tests', 'success'], self.raw_json)
        failures = get_dict_value(['tests', 'failure'], self.raw_json)

        if successes:
            for name in successes:
                job = successes[name]
                if 'tpc-test' in name:
                    self._update_full_mesh(get_dict_value(['task','src'], job), 'src', job)
                    self._update_full_mesh(get_dict_value(['task','dst'], job), 'dst', job)
                elif 'set-up' in name:
                    self._update_full_mesh(get_dict_value(['task','endpoint'], job), name, job)
                elif 'tear-down' in name:
                    self._update_full_mesh(get_dict_value(['task','endpoint'], job), name, job)

        if failures:
            for name in failures:
                job = failures[name]
                if 'tpc-test' in name:
                    self._update_full_mesh(get_dict_value(['task','src'], job), 'src', job)
                    self._update_full_mesh(get_dict_value(['task','dst'], job), 'dst', job)
                elif 'set-up' in name:
                    self._update_full_mesh(get_dict_value(['task','endpoint'], job), name, job)
                elif 'tear-down' in name:
                    self._update_full_mesh(get_dict_value(['task','endpoint'], job), name, job)

        tested = []
        unreachable = []

        sorted_summaries = sorted(self.endpoints.values(), cmp=compare_endpoints_by_rank)
        for summary in sorted_summaries:
            if not summary.setup_succeeded:
                unreachable.append(summary)
            else:
                tested.append(summary)

        self.summary_lines = self._create_full_mesh_summary_output(tested, unreachable)
        path = get_summary_path(self.config, 'full-mesh-summary-name', 'txt')
        print_lines_to_file(path, self.summary_lines)
        return path

    def _create_full_mesh_summary_output(self, tested, unreachable):
        mesh = len(tested)
        total = 0 if mesh == 0 else (mesh - 1)*2

        lines = []
        lines.append("XROOTD FULL MESH TEST SUMMARY")
        lines.append(self.timestamp)
        lines.append("")
        lines.append("Client: %s"%socket.gethostname())
        lines.append("XrootD version: %s"%get_dict_value(['xrootd-settings', 'version'], self.config))
        lines.append("")
        lines.append("Tests per viable endpoint: %s"%total)
        lines.append("")
        
        lines.append("-------------------------------TESTED ENDPOINTS---------------------------------")
        lines.append("")
        
        for summary in tested:
            (typ, score) = get_dict_value([summary.name], self.endpointmap)
            sts = summary.stats(total)
            lines.append(MESH_FORMAT.format(summary.name, typ, 
                                            sts[0], sts[1], sts[2], sts[3],
                                            sts[4], sts[5], sts[6], sts[7],
                                            sts[8], sts[9], sts[10], sts[11], sts[12]))
            lines.append("")
        
        lines.append("------------------------COULD NOT UPLOAD SETUP DATA TO--------------------------")
        lines.append("")
        for summary in unreachable:  
            lines.append(summary.name)
        lines.append("")
        
        lines.append("--------------------------------ERROR DETAILS-----------------------------------")
        lines.append("")

        index = 1
        for summary in tested:
            if summary.has_failures():
                lines.append("[%s] %s"%(index, summary.name))
                failed = summary.failed_as_src
                if len(failed) > 0:
                    lines.append("\tAS SOURCE")
                    for error in failed:
                        lines.append("\t\t%s"%error)
                failed = summary.failed_as_dst
                if len(failed) > 0:
                    lines.append("\tAS DESTINATION")
                    for error in failed:
                        lines.append("\t\t%s"%error)
                lines.append("")
            index += 1

        for summary in unreachable:
            (typ, score) = get_dict_value([summary.name], self.endpointmap)
            lines.append("[%s] %s\t%s"%(index, summary.name, typ))
            lines.append("\tLast error on set-up: %s"%summary.last_error)
            index += 1

        return lines

    def _create_smoke_summary_output(self, total, sound, problematic):
        lines = []
        lines.append("XROOTD SMOKE TEST SUMMARY")
        lines.append(self.timestamp)
        lines.append("")
        lines.append("Client: %s"%socket.gethostname())
        lines.append("XrootD version: %s"%get_dict_value(['xrootd-settings', 'version'], self.config))
        lines.append("")
        lines.append("Reference server: %s"%get_dict_value(['reference-endpoint', 'id'], self.config))
        lines.append("")
        lines.append("Total number of round-trip tests: %s"%total)
        lines.append("")

        lines.append("--------------------------------SOUND ENDPOINTS---------------------------------")
        lines.append("")
        lines.append(SMOKE_FORMAT.format('SCORE', 'ENDPT', 'TYPE', 'UP', 'S_d', 'S_nd', 'D_d', 'D_nd', 'DOWN', ''))
        lines.append("--------------------------------------------------------------------------------")
        for summary in sound:
            (typ, score) = get_dict_value([summary.name], self.endpointmap)
            sts = summary.stats()
            lines.append(SMOKE_FORMAT.format(summary.score, summary.name, typ, 
                                                    sts[0], sts[1], sts[2], sts[3], 
                                                    sts[4], sts[5], sts[6]))

        lines.append("")
        lines.append("-----------------------------PROBLEMATIC ENDPOINTS------------------------------")
        lines.append("")
        lines.append(SMOKE_FORMAT.format('SCORE', 'ENDPT', 'TYPE', 'UP', 'S_d', 'S_nd', 'D_d', 'D_nd', 'DOWN', ''))
        lines.append("--------------------------------------------------------------------------------")
        for summary in problematic:
            (typ, score) = get_dict_value([summary.name], self.endpointmap)
            sts = summary.stats()
            lines.append(SMOKE_FORMAT.format(summary.score, summary.name, typ, 
                                                    sts[0], sts[1], sts[2], sts[3], 
                                                    sts[4], sts[5], sts[6]))
        
        lines.append("")            
        lines.append("--------------------------------ERROR DETAILS-----------------------------------")
        lines.append("")

        index = 1
        for summary in problematic:
            lines.append("[%s] %s"%(index, summary.name))
            errors = summary.errors
            for error in errors:
                lines.append("\t\t%s"%error)
            index += 1
            lines.append("")

        return lines
    
    def _update_full_mesh(self, endpoint, role, job):
        id = get_endpoint_name(endpoint)
        summary = self.endpoints.get(id, None)

        if not summary:
            summary = FullMeshSummary(id, endpoint)
            self.endpoints[id] = summary

        summary.update(role, job)

    def _update_scores(self, config_file):
        config = load_json_configuration(config_file)
        endpoints = get_dict_value(['endpoints'], config)
        for e in endpoints:
            ename = get_dict_value(['id'], e)
            (typ, score) = get_dict_value([ename], self.endpointmap)
            e['score'] = score
        print_json_to_file(config_file, config)

    def _update_smoke(self, endpt_id, task, d, nd):
        summary = self.endpoints.get(endpt_id, None)

        if not summary:
            is_ref = endpt_id == get_endpoint_name(get_dict_value(['reference-endpoint'], self.config))
            summary = SmokeSummary(endpt_id, d, nd, is_ref)
            self.endpoints[endpt_id] = summary

        summary.update(task)

def generate_full_mesh_report(config, multiprocessor_report):
    print_message("Compiling full mesh report ...")
    report = Report(config, None)
    report.create_json_output(multiprocessor_report, 'full-mesh-output-name')
    path = report.create_full_mesh_summary()
    send = get_dict_value(['report', 'send-email'], config)
    if send:
        send_email(path, 
                   "XrootD full mesh test report for %s"%report.timestamp,
                   get_dict_value(['report', 'email-from'], config),
                   get_dict_value(['report', 'email-to'], config),
                   get_dict_value(['report', 'smtp-host'], config))

def generate_smoke_report(config, multiprocessor_report, config_file):
    print_message("Compiling smoke report ...")
    report = Report(config, config_file)
    report.create_json_output(multiprocessor_report, 'smoke-output-name')
    path = report.create_smoke_summary()
    send = get_dict_value(['report', 'send-email'], config)
    if send:
        send_email(path, 
                   "XrootD smoke test report for %s"%report.timestamp,
                   get_dict_value(['report', 'email-from'], config),
                   get_dict_value(['report', 'email-to'], config),
                   get_dict_value(['report', 'smtp-host'], config))
