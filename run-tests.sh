#!/bin/bash

nosetests --with-coverage --cover-erase --cover-package=aioftp --logging-format="%(asctime)s %(message)s" --logging-datefmt="[%H:%M:%S]:" --logging-level=DEBUG
