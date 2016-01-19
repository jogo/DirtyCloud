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
        elif self.email and '@' in self.email:
            domain = self.email.split('@')[1]
            return "%s (%s)" % (self.name, domain)
        else:
            return "%s" % self.name


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


class Graph(object):
    def __init__(self, git_repo):
        super(Graph, self).__init__()
        # Fetch up to date mailmap file
        r = requests.get('http://git.openstack.org/cgit/openstack/stackalytics/plain/etc/default_data.json')
        self.stackalytics = r.json()
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

    def get_node(self, name, company, email, author=False):
        if name not in self.nodes:
            node = self.get_node_by_email(email)
            if not node:
                node = Node(name, company, email)
                self.nodes[name] = node
        else:
            node = self.nodes[name]
        if author:
            # author emails are more accurate
            node.email = email
        if company and not node.company:
            node.company = company
        return node

    def get_stackalytics_user_name(self, email):
        for user in self.stackalytics["users"]:
            if email.lower() in [a.lower() for a in list(user['emails'])]:
                for company in user['companies']:
                    if not company['end_date']:
                        return (user['user_name'], company['company_name'])
                return (user['user_name'], None)
        return (None, None)

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


class GerritGraph(Graph):
    def __init__(self, git_repo, repo_name):
        super(GerritGraph, self).__init__(git_repo=git_repo)
        # TODO emit some sort of progress information
        self.change_ids = self.get_git_change_ids()
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
        futures = []
        for change_id in self.change_ids:
            url = ("https://review.openstack.org:443/changes/%s~master~%s/detail"
                   % (urllib.parse.quote_plus(self.repo_name), change_id))
            future = self.session.get(url)
            futures.append(future)
        for future in futures:
            r = future.result()
            try:
                if r.text.startswith("Not found: "):
                    # Something went wrong, found a commit that doesn't have a record of
                    # being submitted to master.
                    return None
                data = json.loads(r.text[4:])
            except ValueError:
                print(r.text)
                raise
            author = data['owner']
            core_reviewers = []
            for message in data['messages']:
                if "Code-Review+2" in message['message']:
                    core_reviewers.append(message['author'])

            # TODO add company support (move company lookup into Node)
            author_node = self.get_node(author['name'], None, author.get('email'), author=True)
            author_node.patch_count += 1
            for reviewer in core_reviewers:
                reviewer_node = self.get_node(reviewer['name'], None, reviewer.get('email'))
                reviewer_node.review_count += 1
                self.increment_edge(reviewer_node, author_node)

    def clean_edges(self):
        # TODO make this more robust
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


# TODO decide if git only mode should be kept
class GitGraph(Graph):
    """Extract gerrit +2 reviews from  git logs with notes.

    Core reviewer defined as someone who can do "Code-Review+2: ".
    Generates a list of edges: (Reviewer, Author)
    """

    def __init__(self, git_repo):
        super(GitGraph, self).__init__(git_repo=git_repo)
        self.commits = self.get_git_commits()
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

    def parse_commit(self, commit):
        """Extract author and +2 reviewers from commit."""
        for line in commit.split('\n'):
            if line.startswith("Author: "):
                name, company, email = self.parse_git_logs(line)
                author = self.get_node(name, company, email, author=True)
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
                name, company, email = self.parse_git_logs(line)
                reviewers.append(self.get_node(name, company, email))
        return reviewers

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
