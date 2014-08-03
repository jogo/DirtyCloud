Idea
====

Discover (OpenStack's) human review networks.

The networks of reviewers and patch authors can reveal interesting details
about the politics and social network of a project.

Reading the Graph
=================


Nodes: Reviewers (Red:Core, Blue: Other)

Edges: Reviews from A of B's work.

  * Wider end of line is the target (B)
  * Edge strength (strongest to weakest)

    * Green lines
    * Solid Blue
    * Dotted Blue

Data Source: Gerrit notes. So only +2s on the final revision of a patch that
landed is counted.

Usage
=====

See `./graph.py -h`
