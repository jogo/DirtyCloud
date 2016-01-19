# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests

import collections
import os
import subprocess

import names

unique_names = []


class Node(object):
    def __init__(self, name, company, email):
        super(Node, self).__init__()
        self.name = repr(name)
        self.company = company
        self.email = email
        self.review_count = 0
        self.patch_count = 0

    def is_core(self):
        # Since currently only using git notes this isn't precise
        return self.review_count > 3

    def __repr__(self):
        if self.company:
            return "%s (%s)" % (self.name, self.company)
        else:
            domain = self.email.split('@')[1]
            return "%s (%s)" % (self.name, domain)

    def __str__(self):
        if self.company:
            return "%s\n(%s)" % (self.name, self.company)
        else:
            domain = self.email.split('@')[1]
            return "%s\n(%s)" % (self.name, domain)


class AnonNode(Node):
    def __init__(self, name, company, email):
        super(AnonNode, self).__init__(name, company, email)
        unique = False
        while not unique:
            random_name = names.get_first_name()
            if random_name not in unique_names:
                unique = True
                unique_names.append(random_name)
                self.fake_name = random_name

    def __repr__(self):
        return "%s" % self.fake_name

    def __str__(self):
        return "%s" % self.fake_name


class RawGitGraph(object):
    """Extract gerrit +2 reviews from  git logs with notes.

    Core reviewer defined as someone who can do "Code-Review+2: ".
    Generates a list of edges: (Reviewer, Author)
    """

    def __init__(self, git_repo, pseudonyms=False):
        super(RawGitGraph, self).__init__()
        # up to date mailmap file
        # http://git.openstack.org/cgit/stackforge/stackalytics/plain/etc/default_data.json
        r = requests.get('http://git.openstack.org/cgit/stackforge/stackalytics/plain/etc/default_data.json')
        self.stackalytics = r.json()
        self.git_repo = git_repo
        self.nodes = dict()  # string:node_object
        if pseudonyms:
            self.node_class = AnonNode
        else:
            self.node_class = Node
        self.commits = self.get_git_commits()
        self.unweighted_graph = self.generate_raw_git_graph()

    def get_git_commits(self):
        """Get git log with gerrit notes."""
        cwd = os.getcwd()
        os.chdir(self.git_repo)
        # gerrit ref for notes
        command = ("git log --notes=refs/notes/review "
                   "--no-merges --since=6.month")
        log = subprocess.check_output(command.split(' '))
        os.chdir(cwd)
        commits = log.split("\ncommit ")
        return commits

    def generate_raw_git_graph(self):
        """Generate list of edges based on git logs.

        list = [(Reviewer,Author),(Reviewer2, Author)]
        """
        edges = []
        for commit in self.commits:
            edge = self.parse_commit(commit)
            if len(edge) == 0:
                # something went wrong
                continue
            edges = edges + edge
        return edges

    def get_node_by_email(self, email):
        """Look up node by email."""
        for node in self.nodes.values():
            if email == node.email:
                return node
        return None

    def parse_commit(self, commit):
        """Extract author and +2 reviewers from commit."""
        edges = []
        for line in commit.split('\n'):
            if line.startswith("Author: "):
                author = self.get_node(line, author=True)
                author.patch_count += 1
                break
        for reviewer in self.get_core_reviewers_on_commit(commit):
            reviewer.review_count += 1
            edges.append((reviewer, author))
        return edges

    def get_core_reviewers_on_commit(self, commit):
        """Extract core reviewers on a specific commit."""
        reviewers = []
        notes = False
        for line in commit.split('\n'):
            if line.strip() == "Notes (review):":
                # Make sure we ignore the git commit message
                notes = True
            elif notes and "Code-Review+2: " in line:
                reviewers.append(self.get_node(line))
        return reviewers

    def get_node(self, line, author=False):
        name, company, email = self.parse_git_logs(line)
        if name not in self.nodes:
            node = self.get_node_by_email(email)
            if not node:
                node = self.node_class(name, company, email)
                self.nodes[name] = node
        else:
            node = self.nodes[name]
        if author:
            # author emails are more accurate
            node.email = email
        if company and not node.company:
            node.company = company
        return node

    def parse_git_logs(self, line):
        """Parse git log to find name and email."""
        # https://github.com/networkx/networkx/issues/1230
        email = line.split()[-1][1:-1]
        name = ' '.join(line.split()[1:-1])
        name_lookup, company = self.get_stackalytics_user_name(email)
        if not name_lookup:
            return name, company, email
        else:
            return name_lookup, company, email

    def get_stackalytics_user_name(self, email):
        for user in self.stackalytics["users"]:
            if email.lower() in [a.lower() for a in list(user['emails'])]:
                for company in user['companies']:
                    if not company['end_date']:
                        return (user['user_name'], company['company_name'])
                return (user['user_name'], None)
        return (None, None)


class ProcessedGitGraph(RawGitGraph):
    def __init__(self, git_repo, pseudonyms=False):
        super(ProcessedGitGraph, self).__init__(git_repo=git_repo, pseudonyms=pseudonyms)
        self.weighted_graph = self.weight_graph()

    def count_edges(self):
        # key: (Reviewer,Author), value:edge count
        weighted = collections.defaultdict(float)
        # weigh edges
        for edge in self.unweighted_graph:
            weighted[edge] += 1
        return weighted

    def weight_graph(self):
        """Assign weights to edges.

        Weight of edge ReviewerA->AuthorB:
        weight = (# duplicate edges)/(# of reviews by ReviewerA)
        """
        # key: (Reviewer,Author), value:weight
        weighted = self.count_edges()
        # normalize weights by total reviews per reviewer
        for edge in weighted:
            weighted[edge] = weighted[edge] / edge[0].review_count
        # clean up data
        hit_list = set([])
        for edge in weighted:
            # sanity check, if any weights are 1, remove.
            if weighted[edge] > 0.99:
                hit_list.add(edge)
            # if reviewer has less then 3 core reviews, probably
            # not a core
            if not edge[0].is_core():
                hit_list.add(edge)
            # if author core and less then x commits
            if (not edge[1].is_core() and edge[1].patch_count < 10):
                hit_list.add(edge)
        for hit in hit_list:
            del weighted[hit]
        return weighted

    def get_strongest_edges(self, n=20):
        """"Return list with top n strongest edges with raw edge numbers."""
        # Get raw numbers
        raw = dict()
        edge_count = self.count_edges()
        for key in self.weighted_graph.keys():
            reviewer = key[0]
            raw[key] = (edge_count[key], reviewer.review_count)
        # Sort dict by key
        strongest = sorted(raw.iteritems(), key=lambda x: (x[1][0] / x[1][1]),
                           reverse=True)
        return strongest[:n]

    def print_records(self):
        # TODO revise to use networkx (edges can be objects)
        print("((Reviewer, Author)): weight (hits/reviews))")
        for x in self.get_strongest_edges():
            key, (hits, reviews) = x
            print("'%s': %f (%d/%d)" % (key, hits / reviews, hits, reviews, ))
