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

import os
import subprocess

import names

unique_names = []


class Node(object):
    def __init__(self, name, company, email):
        super(Node, self).__init__()
        self.name = name
        self.company = company
        self.email = email
        # TODO username
        self.review_count = 0
        self.patch_count = 0

    def is_core(self):
        # if reviewer has less then 3 core reviews, probably
        # not a core
        # Since currently only using git notes this isn't precise
        return self.review_count > 20

    def __repr__(self):
        if self.company:
            return "%s (%s)" % (self.name, self.company)
        else:
            domain = self.email.split('@')[1]
            return "%s (%s)" % (self.name, domain)

    def __str__(self):
        if self.company:
            return "%s (%s)" % (self.name, self.company)
        else:
            domain = self.email.split('@')[1]
            return "%s (%s)" % (self.name, domain)


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


class Edge(object):
    def __init__(self, reviewer, author):
        super(Edge, self).__init__()
        self.reviewer = reviewer
        self.author = author
        self.count = 1

    def __str__(self):
        return "%s -> %s" % (self.reviewer, self.author)

    def score(self):
        return self.count / self.reviewer.review_count


class GitGraph(object):
    """Extract gerrit +2 reviews from  git logs with notes.

    Core reviewer defined as someone who can do "Code-Review+2: ".
    Generates a list of edges: (Reviewer, Author)
    """

    def __init__(self, git_repo, pseudonyms=False):
        super(GitGraph, self).__init__()
        # Fetch up to date mailmap file
        r = requests.get('http://git.openstack.org/cgit/openstack/stackalytics/plain/etc/default_data.json')
        self.stackalytics = r.json()
        self.git_repo = git_repo
        self.nodes = dict()  # string:node_object
        if pseudonyms:
            self.node_class = AnonNode
        else:
            self.node_class = Node
        self.commits = self.get_git_commits()
        self.edges = []
        self.generate_edges()
        self.clean_edges()

    def get_git_commits(self):
        """Get git log with gerrit notes."""
        cwd = os.getcwd()
        os.chdir(self.git_repo)
        # gerrit ref for notes
        command = ("git log --notes=refs/notes/review "
                   "--no-merges --since=6.month")
        log = subprocess.check_output(command.split(' ')).decode("utf-8")
        os.chdir(cwd)
        commits = log.split("\ncommit ")
        return commits

    def generate_edges(self):
        """Generate list of edges based on git logs."""
        for commit in self.commits:
            self.parse_commit(commit)

    def get_node_by_email(self, email):
        """Look up node by email."""
        for node in self.nodes.values():
            if email == node.email:
                return node
        return None

    def parse_commit(self, commit):
        """Extract author and +2 reviewers from commit."""
        for line in commit.split('\n'):
            if line.startswith("Author: "):
                author = self.get_node(line, author=True)
                author.patch_count += 1
                break
        for reviewer in self.get_core_reviewers_on_commit(commit):
            reviewer.review_count += 1
            self.increment_edge(reviewer, author)

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

    def increment_edge(self, reviewer, author):
        """If edge already exists, increase count, else add new edge"""
        # Look for existing edge
        for edge in self.edges:
            if edge.reviewer == reviewer and edge.author == author:
                edge.count += 1
                return edge
        edge = Edge(reviewer=reviewer, author=author)
        self.edges.append(edge)
        return edge

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

    def clean_edges(self):
        # TODO make this more robust
        hit_list = []
        for edge in self.edges:
            # sanity check, if any weights are 1, remove.
            if edge.score() > 0.99:
                hit_list.append(edge)
            elif not edge.reviewer.is_core():
                hit_list.append(edge)
            # if author core and less then x commits
            elif (not edge.author.is_core() and edge.author.patch_count < 10):
                hit_list.append(edge)
        for hit in hit_list:
            self.edges.remove(hit)

    def get_strongest_edges(self, n=20):
        """"Return list with top n strongest edges with raw edge numbers."""
        # Sort dict by key
        strongest = sorted(self.edges,
                           key=lambda edge: edge.score(),
                           reverse=True)
        return strongest[:n]

    def print_records(self):
        print("((Reviewer, Author)): weight (hits/reviews))")
        for edge in self.get_strongest_edges():
            print("'%s': %f (%d/%d)" % (edge, edge.score(),
                                        edge.count, edge.reviewer.review_count))
