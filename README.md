# TubeArchivist Plex Integration

This is a custom set of Scanner and Agent to integrate [TubeArchivist](https://github.com/tubearchivist/tubearchivist) with Plex.

# Limitations
This is a custom scanner and agent combination. It is expected that you have both the scanner and agent running with Plex in order for it to properly parse the necessary details for pulling in the metadata.

The scanner and agent can only be used to integrate with a single TubeArchivist instance. Additional instance support might have to be built into a future version of the integration.

This pulls a lot of the metadata details directly from TubeArchivist, so TubeArchivist must be running during filesystem scans and metadata refreshes. If it is unable to access TubeArchivist, then it will either attempt to keep what details it currently has or cause exceptions to rise, skipping those files.

This is an early build, so there might be issues with detecting certain feature components. Issues with Feature Requests are recommended to document the request, however we may be unable to fulfill all requests without additional help and support. Pull Requests for features to add functionality or fix issues are welcome.

Playlist integration is an expected roadmap item but is not currently available.

Not all metadata that Plex can show is being provided at this time and will be incorporate with future releases.

# Installation Steps
## Plex Media Server Location
The root `Plex Media Server` directory can be in different locations depending on how it is installed. All references for installation will be based on this location.

Article: [How Do I Manually Install A Plugin?](https://support.plex.tv/articles/201187656-how-do-i-manually-install-a-plugin/)

Article: [How Do I Find the Plug-ins Folder?](https://support.plex.tv/articles/201106098-how-do-i-find-the-plug-ins-folder/)

Article: [Where Is The Plex MediaServer Data Directory Located?](https://support.plex.tv/articles/202915258-where-is-the-plex-media-server-data-directory-located/)

A list of potential default installation locations:


    * '%LOCALAPPDATA%\Plex Media Server\'                                        # Windows Vista/7/8
    * '%USERPROFILE%\Local Settings\Application Data\Plex Media Server\'         # Windows XP, 2003, Home Server
    * '$HOME/Library/Application Support/Plex Media Server/'                     # Mac OS
    * '$PLEX_HOME/Library/Application Support/Plex Media Server/',               # Linux
    * '/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/', # Debian,Fedora,CentOS,Ubuntu
    * '/usr/local/plexdata/Plex Media Server/',                                  # FreeBSD
    * '/usr/pbi/plexmediaserver-amd64/plexdata/Plex Media Server/',              # FreeNAS
    * '${JAIL_ROOT}/var/db/plexdata/Plex Media Server/',                         # FreeNAS
    * '/c/.plex/Library/Application Support/Plex Media Server/',                 # ReadyNAS
    * '/share/MD0_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server/',        # QNAP
    * '/volume1/Plex/Library/Application Support/Plex Media Server/',            # Synology, Asustor
    * '/raid0/data/module/Plex/sys/Plex Media Server/',                          # Thecus
    * '/raid0/data/PLEX_CONFIG/Plex Media Server/'                               # Thecus Plex community

## First time setup preparations
1. Pull the [API Key](https://docs.tubearchivist.com/settings/#integrations) for TubeArchivist and have it ready for the configuration files.
2. Ensure that Plex can see the Media directory that you will use to store the videos.
3. Ensure that the system running Plex can communicate to TubeArchivist.

## Download `.zip` File
1. Download the Zip File: https://github.com/tubearchivist/tubearchivist-plex/archive/refs/heads/main.zip
2. Unpack the Zip File.
3. Rename the unpacked directory to `TubeArchivist-Agent.bundle`.

## Scanner Installation
> [!NOTE]
> The `Scanners` and `Series` folders are not created by default. If this is your first time using a Scanner, follow the instructions as-is.

1. Inside the `TubeArchivist-Agent.bundle`, move the subdirectory `Scanners` into the `Plex Media Server` directory.
2. Inside the `Scanners\Series` directory, rename or copy the `sample-ta-config.json` to `ta-config.json`.
3. Update the configurations within the `ta-config.json` file to reflect your settings for connecting to the TubeArchivist instance and its [API Key](https://docs.tubearchivist.com/settings/#integrations).
4. Change the ownership and permissions of both the Python script and configuration JSON file to allow access to the Plex user that is appropriate for your system. This should match most other files already in the `Plex Media Server` directory.
5. After you have placed the Agent, you will restart the Plex Media Server service.

## Agent Installation
1. If there is still a `Scanners` folder in the `TubeArchivist-Agent.bundle` directory, go ahead and move/remove it.
2. Move the `TubeArchivist-Agent.bundle` directory into the `Plex Media Server\Plug-ins` directory.
3. Change the ownership and permissions of the directory and all subdirectories/files to allow access to teh Plex user that is appropriate for your system. This should match the other Agent bundles that are already in the `Plex Media Server\Plug-ins` directory.
4. Restart the Plex Media Server service as is appropriate for your system.

## Library Integration
1. After the Scanner and Agent have been installed, create a new (or update an existing) library.
2. Choose the `Manage Library` -> `Edit...` option.
3. On the `General` tab, select the `TV Shows` option.
4. On the `Advanced` tab, select or update the following mandatory options:
    * Scanner: `TubeArchivist Scanner`
    * Agent: `TubeArchivist Agent`
    * TubeArchivist API Key: Insert the API Key (this is the same that is used for the Scanner config file)
    * TubeArchivist URL: The URL that Plex can access your TubeArchivist instance
5. The Scanner should immediately start finding new videos and update as it sees them, but you can also run a `Scan Library Files` for the Library to initiate a check.
6. The Agent should update the metadata after finding the new videos, but you can also run a `Refresh Metadata` on the Library, Channel, or individual video to initiate an update.

# Troubleshooting
If you are having problems with seeing the Scanner or Agent, confirm that the instructions are followed.
If the Scanner and Agent are selected, but you are not seeing videos, then it could mean that the Scanner is having a problem. Check the Scanner Logs to get more information.
If the Scanner and Agent are selected, but the channels or videos are not pulling in thumbnails, correct titles, or having other issues with the metadata, then it could mean that the Agent is having a problem. Check the Agent Logs to get more information.

# Log Locations
Scanner Log Location: `Plex Media Server/Logs/TubeArchivist Scanner`, default file is `_root_.scanner.log`

Agent Log Location: `Plex Media Server/Logs/PMS Plugin Logs/com.plexapp.agents.tubearchivist_agent.log`

# Issues
If you are still having an issue, either open an Issue in GitHub or a Support Case on the Discord, specifying that it is related to the Plex integration.

# Special Thanks and Reference
This project is heavily influenced by the works of ZeroQI, JordyAlkema, and BeefTornado, as well as the Plex Media Server's official scanners and agents. 