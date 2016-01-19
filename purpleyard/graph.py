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


def render_graph(graph, name):
    """Generate a json file for graphing in d3.

    :param GerritGraph graph: graph to render
    """
    # convert to list of nodes and edges
    nodes = []
    edges = []
    for edge in graph.get_strongest_edges(10):
        if edge.reviewer not in nodes:
            nodes.append(edge.reviewer)
        if edge.author not in nodes:
            nodes.append(edge.author)
        edge_dict = edge.to_dict()
        edge_dict['source'] = nodes.index(edge.reviewer)
        edge_dict['target'] = nodes.index(edge.author)
        edges.append(edge_dict)

    # convert node to target format
    json_nodes = []
    orgs = []
    for node in nodes:
        node_dict = node.to_dict()
        if not node.company:
            # use email
            if node.email not in orgs:
                orgs.append(node.email)
            node_dict['group'] = orgs.index(node.email)
        else:
            if node.company not in orgs:
                orgs.append(node.company)
            node_dict['group'] = orgs.index(node.company)
        json_nodes.append(node_dict)

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
    graph = gitlogs.GerritGraph(git_repo=repo_path, repo_name=options.repository)
    graph.print_records()
    render_graph(graph,
                 options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
