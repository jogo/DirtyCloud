import collections
import os
import random
import subprocess


class RawGitGraph(object):
    """Extract gerrit +2 reviews from  git logs with notes.

    Only use commits where the author is a core reviewer,
    otherwise the graphs becomes unwieldy.
    Core reviewer defined as someone who can do "Code-Review+2: ".
    Generates a list of edges: (Reviewer, Author)
    """

    def __init__(self, git_repo='/home/jogo/Develop/openstack/nova'):
        super(RawGitGraph, self).__init__()
        self.git_repo = git_repo
        self.commits = self.get_git_commits()
        self.core_reviewers = self.get_core_reviewers()
        self.unweighted_graph = self.generate_raw_git_graph()
        # TODO(jogo) add mailmap support for author and reviewers

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
            # if author is a core reviewer
            if edge[0][1] in self.core_reviewers:
                edges = edges + edge
        return edges

    def get_core_reviewers(self):
        """Return a list of core reviewers with review count.

        On all commits, not just patches by a core
        """
        cores = collections.defaultdict(int)
        for commit in self.commits:
            for core in self.get_core_reviewers_on_commit(commit):
                cores[core] += 1
        return dict(cores)

    def parse_commit(self, commit):
        """Extract author and +2 reviewers from commit."""
        edges = []
        for line in commit.split('\n'):
            if line.startswith("Author: "):
                author = self.get_email(line)
                break
        for reviewer in self.get_core_reviewers_on_commit(commit):
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
                reviewers.append(self.get_email(line))
        return reviewers

    def get_email(self, line):
        """Parse git log to find email."""
        return line.split()[-1]


class ProcessedGitGraph(RawGitGraph):
    def __init__(self, git_repo):
        super(ProcessedGitGraph, self).__init__(git_repo=git_repo)
        self.weighted_graph = self.weight_graph()

    def weight_graph(self):
        """Assign weights to edges.

        Weight of edge ReviewerA->AuthorB:
        weight = (# duplicate edges)/(# of reviews by ReviewerA)
        """
        # key: (Reviewer,Author), value:weight
        weighted = collections.defaultdict(float)
        # weigh edges
        for edge in self.unweighted_graph:
            weighted[edge] += 1
        # normalize weights by total reviews per reviewer
        for edge in weighted:
            weighted[edge] = weighted[edge]/self.core_reviewers[edge[0]]
        return weighted

    def get_weight_range(self):
        min_weight = min(self.weighted_graph.values())
        max_weight = max(self.weighted_graph.values())
        return (min_weight, max_weight)

    def get_strongest_edges(self, n=5):
        """"Return list with top n strongest edges."""
        # Sort dict by key
        strongest = sorted(self.weighted_graph.iteritems(), key=lambda x: x[1],
                           reverse=True)
        return strongest[:n]


class AnonimizedGitGraph(ProcessedGitGraph):
    """Replace emails with pseudonyms."""

    def __init__(self, git_repo):
        random.seed()
        self.email_map = dict()
        super(AnonimizedGitGraph, self).__init__(git_repo=git_repo)

    def get_email(self, line):
        """Parse git log to find email."""
        email = super(AnonimizedGitGraph, self).get_email(line)
        return self.anonimize_email(email)

    def anonimize_email(self, email):
        # anonimize
        if email not in self.email_map:
            self.email_map[email] = self.get_unique_random_name()
        return self.email_map[email]

    def get_unique_random_name(self, n=1000):
        # Generate up to n random names
        if len(self.email_map) is n:
            # no more random names left in space
            raise Exception("No more random names left")
        while True:
            rand = str(int(random.random()*n))
            if rand not in self.email_map.values():
                return rand
