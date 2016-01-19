Idea
====

Discover (OpenStack's) human review networks.

The networks of reviewers and patch authors can reveal interesting details
about the politics and social network of a project.

Usage
=====

Update purple.ini

Make sure your source git repos are up to date

Run `tox -erun -- h` options.

That will generate a git.json file, to view the results run

`python -m SimpleHTTPServer` and go to http://localhost:8000/index.html
