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


def generate_graph(gitgraph, name):
    """Generate a json file for graphing in d3.

    Args:
        gitgraph (): ProcessedGitGraph
        name (bool): repo name
    """
    # convert to list of nodes and edges
    nodes = []
    edges = []
    for edge in gitgraph.get_strongest_edges(10):
        if edge.reviewer not in nodes:
            nodes.append(edge.reviewer)
        if edge.author not in nodes:
            nodes.append(edge.author)

        edges.append({"source": nodes.index(edge.reviewer),
                      "target": nodes.index(edge.author),
                      "value": edge.score()})

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
    options, args = optparser.parse_args()

    config = configparser.ConfigParser()
    config.read('purple.ini')

    repo_path = config.get("config", "git_path") + options.repository
    gitgraph = gitlogs.GerritGraph(git_repo=repo_path, repo_name=options.repository)
    # gitgraph = gitlogs.GitGraph(git_repo=repo_path)
    gitgraph.print_records()
    generate_graph(gitgraph,
                   options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
