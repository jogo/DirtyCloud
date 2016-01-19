#!/usr/bin/env python

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

import configparser
import json
import optparse

from purpleyard import gitlogs


# TODO convert to emit JSON and use D3 (see d3.html)
# TODO cleanup if d3 looks good
def generate_graph(gitgraph, save, name):
    """Generate a json file for graphing in d3 .

    Args:
        gitgraph (): ProcessedGitGraph
        save (bool): True to safe graph as a png file
        name (bool): repo name
    """
    # convert to list of nodes and edges
    nodes = []
    edges = []
    for edge in gitgraph.get_strongest_edges():
        (reviewer, author), (hits, reviews) = edge
        if reviewer not in nodes:
            nodes.append(reviewer)
        if author not in nodes:
            nodes.append(author)

        edges.append({"source": nodes.index(reviewer),
                      "target": nodes.index(author),
                      "value": hits / reviews})

    # convert node to target format
    json_nodes = []
    orgs = []
    for node in nodes:
        if not node.company:
            # use email
            if node.email not in orgs:
                orgs.append(node.email)
            json_nodes.append({'name': node.name, 'group': orgs.index(node.email)})
        else:
            if node.company not in orgs:
                orgs.append(node.company)
            json_nodes.append({'name': node.name, 'group': orgs.index(node.company)})

    # convert to json
    with open('git.json', 'w') as f:
        json.dump({"links": edges, "nodes": json_nodes}, f)


def main():
    optparser = optparse.OptionParser()
    optparser.add_option('-r', '--repository',
                         default='openstack/nova',
                         help='specify repository to analyze')
    optparser.add_option('-p', '--pseudonyms',
                         action='store_true',
                         help='Use pseudonyms instead of email addresses')
    optparser.add_option('-s', '--save',
                         action='store_true',
                         help='Save image')
    optparser.add_option('-t', '--no-graph',
                         action='store_true',
                         help="Just print records, don't generate the graph")
    options, args = optparser.parse_args()

    config = configparser.ConfigParser()
    config.read('purple.ini')

    repo_path = config.get("config", "git_path") + options.repository

    gitgraph = gitlogs.ProcessedGitGraph(git_repo=repo_path, pseudonyms=options.pseudonyms)

    gitgraph.print_records()

    if not options.no_graph:
        generate_graph(gitgraph,
                       options.save,
                       options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
