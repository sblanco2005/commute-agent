# Claude Code - Commuteapp

This file contains information about the Commuteapp project for Claude Code.

## Project Overview

Commuteapp is a commute management application that helps users track and manage their public transportation usage.

## Key Components

- **Agent**: Contains client implementations for various transportation services
  - `rail_client.py`: Rail transportation client
  - `subway.py`: Subway transportation client
  - `auto_trigger.py`: Automated trigger functionality

- **API**: Server implementation
  - `server.py`: Main API server

## Technologies

- Python-based application
- RESTful API architecture
- Integration with public transportation services

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Configure authentication tokens as needed
3. Run the API server: `python api/server.py`

## Notes

- Token files should be kept secure and not committed to version control
- The project uses git for version control
