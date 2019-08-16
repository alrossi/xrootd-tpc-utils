# xrootd-tpc-utils

<!-- COPYRIGHT STATUS:
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
documents or software obtained from this server. -->

System tests to test viability of xrootd third-party copy between endpoints.

There are two types of test: 

    (a) "Full Mesh":   A data file is uploaded to each endpoint, and
                       then transferred both ways between endpoint pairs.

    (b) "Smoke":       An endpoint is selected as reference; for all other
                       endpoints, a file is uploaded, transferred to the
                       reference endpoint, transferred back, and then
                       downloaded from the endpoint.
                       
See also the info in the xrootd_tests script by doing:

        python xrootd_tests -i

-------------------------------------------------------------------------------

Configuration and Output

The test suite requires a .json configuration file.  Some examples are given
in the conf directory.

Most of the settings should be self-explanatory.  For the "test-phases",
"capture-streams" means that the streams from the xrootd executable will be
redirected to their own log file in the indicated log directory 
(see under "report").  For the tpc phase, one can try with delegation,
without delegation, or both.

The full-mesh version of the tests uses the upload phase to place the 
data file on all endpoints, and the remove phase to delete it from the
endpoints.

The output from each test suite run is in the form of another .json file
which records the (extended) configuration instance, plus the metadata for
each task in the suite, including all out or err lines which appear to 
indicate errors.   

The summary file is a plain text condensation of the results with some
basic statistical information (percentage of successes in the case of 
the full mesh, number of successful hops in the smoke test), followed
by a listing of the individual failures for each endpoint with the
last error reported for each.  See the examples directory for
example output.  The example.log file shows typical output from 
the script with the -d (debug) option.

The summary file can be emailed using the local smtp server if it
exists; the 'to' takes a list of recipient addresses.

The configuration allows for automated generation of the x509 proxy
(see under "gsi-settings", provided permissions for the script user
are correct) and test data (see under "local-data-file")
using the unix/linux 'dd' command.

Full-mesh output ranks the endpoints by their percentage of successes;
the smoke test classifies them as sound (all tests passed)
or problematic.  The score in the smoke test is a running sum 
from 0 to 20 updated after each test suite run (to the config file),
and reflects how reliable the endpoint is.  If it passes all tests,
its score is incremented by 1, up to the maximum.  Failing a test
decrements it by 1.

-------------------------------------------------------------------------------

The python code was written for version 2.7.

A local pip wheel dist is provided for local installation via:

        python -m pip install dist/xrootdtests-1.0-py2-none-any.whl

Note that Python.org sites stopped supporting TLS version 1.0 and 1.1, which 
could cause issues if you try to update pip wheel on your platform.

In this case, a suggested solution is to upgrade pip without using pip:

        curl https://bootstrap.pypa.io/get-pip.py | python
