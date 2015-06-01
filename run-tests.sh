#!/bin/bash

ls -d tests/*/ | xargs rm -rdf
nosetests --stop --with-coverage --cover-erase --cover-package=aioftp --logging-format="%(asctime)s %(message)s" --logging-datefmt="[%H:%M:%S]:" --logging-level=INFO
