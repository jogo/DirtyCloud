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
import requests_futures.sessions

import json
import os
import subprocess
import urllib.parse


class Node(object):
    """Node in Graph"""
    # Fetch up to date mailmap file
    r = requests.get('http://git.openstack.org/cgit/openstack/stackalytics/plain/etc/default_data.json')
    stackalytics = r.json()

    def __init__(self, name, email):
        super(Node, self).__init__()
        self.name = name
        self.email = email
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
        elif self.email and '@' in self.email:
            domain = self.domain
            return "%s (%s)" % (self.name, domain)
        else:
            return "%s" % self.name

    def to_dict(self):
        return {'name': self.name, 'review_count': self.review_count,
                'patch_count': self.patch_count,
                'company': self.company}

    @property
    def domain(self):
        """email domain"""
        return self.email.split('@')[1]

    @property
    def company(self):
        if not self.email:
            return None
        # check users
        for user in self.stackalytics["users"]:
            if self.email.lower() in [a.lower() for a in list(user['emails'])]:
                for company in user['companies']:
                    if not company['end_date']:
                        return company['company_name']
        # check email domains
        for company in self.stackalytics["companies"]:
            # domain substring matching
            if any([domain and self.domain.endswith(domain) for domain in company["domains"]]):
                return company["company_name"]

        return None


class Edge(object):
    """Edge in graph

    Connects reviewer to author
    """
    def __init__(self, reviewer, author):
        super(Edge, self).__init__()
        self.reviewer = reviewer
        self.author = author
        self.count = 1

    def __str__(self):
        return "%s -> %s" % (self.reviewer, self.author)

    def score(self):
        return self.count / self.reviewer.review_count

    def to_dict(self):
        return {'count': self.count, 'str': self.__str__(),
                'value': self.score(),
                'reviewer_count': self.reviewer.review_count}


class Graph(object):
    def __init__(self, git_repo):
        super(Graph, self).__init__()
        self.git_repo = git_repo
        self.nodes = dict()  # string:node_object
        self.edges = []

    def get_node_by_email(self, email):
        """Look up node by email."""
        for node in self.nodes.values():
            if email == node.email:
                return node
        return None

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

    def get_node(self, name, email):
        if name not in self.nodes:
            node = self.get_node_by_email(email)
            if not node:
                node = Node(name, email)
                self.nodes[name] = node
        else:
            node = self.nodes[name]
        if email and not node.email:
            node.email = email
        return node

    def get_strongest_edges(self, percent=10):
        """"Return list with top n strongest edges with raw edge numbers."""
        # Sort dict by key
        strongest = sorted(self.edges,
                           key=lambda edge: edge.score(),
                           reverse=True)
        strongest = filter(lambda edge: edge.score() * 100 > percent, strongest)
        return strongest

    def print_records(self):
        print("((Reviewer, Author)): weight (hits/reviews))")
        for edge in self.get_strongest_edges():
            print("'%s': %f (%d/%d)" % (edge, edge.score(),
                                        edge.count, edge.reviewer.review_count))


class GerritGraph(Graph):
    """Graph based in gerrit review data."""
    def __init__(self, git_repo, repo_name):
        super(GerritGraph, self).__init__(git_repo=git_repo)
        self.change_ids = self.get_git_change_ids()
        print("found %s changes" % len(self.change_ids))
        self.repo_name = repo_name
        self.session = requests_futures.sessions.FuturesSession(max_workers=2)
        self.populate_graph()
        self.clean_edges()

    def get_git_change_ids(self):
        """Get git log with gerrit notes."""
        cwd = os.getcwd()
        os.chdir(self.git_repo)
        # gerrit ref for notes
        command = ("git log --no-merges --since=6.month origin/master")
        log = subprocess.check_output(command.split(' ')).decode("utf-8")
        os.chdir(cwd)
        change_ids = []
        change_id = "Change-Id: "
        for commit in log.split("\ncommit "):
            for line in commit.split('\n'):
                if line.strip().startswith(change_id):
                    change_ids.append(line.split(change_id)[1])
        return change_ids

    def populate_graph(self):
        """Fetch author and core reviewers who +2ed any revision.

        Pass in list of change_ids for a single project.
        Track users by email.
        """
        total = len(self.change_ids)
        futures = []
        for change_id in self.change_ids:
            url = ("https://review.openstack.org:443/changes/%s~master~%s/detail"
                   % (urllib.parse.quote_plus(self.repo_name), change_id))
            future = self.session.get(url)
            futures.append(future)
        for i, future in enumerate(futures):
            if i > 0 and i % 100 == 0:
                print("%0d%% done ..." % (float(i) / total * 100))
            r = future.result()
            try:
                if r.text.startswith("Not found: "):
                    # Something went wrong, found a commit that doesn't have a record of
                    # being submitted to master.
                    print("change id not found, skipping")
                    continue
                data = json.loads(r.text[4:])
            except ValueError:
                print(r.text)
                raise
            author = data['owner']
            core_reviewers = []
            for message in data['messages']:
                if "Code-Review+2" in message['message']:
                    core_reviewers.append(message['author'])

            author_node = self.get_node(author['name'], author.get('email'))
            author_node.patch_count += 1
            for reviewer in core_reviewers:
                reviewer_node = self.get_node(reviewer['name'], reviewer.get('email'))
                reviewer_node.review_count += 1
                self.increment_edge(reviewer_node, author_node)

    def clean_edges(self):
        # Adjust for gerrit
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
