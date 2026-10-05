---
source: https://www.construct.net/en/tutorials/constructs-project-format-3275
title: Construct's project format
authors: Ashley (Construct Team, Founder); DiegoM (Construct Team, Construct 3 Developer)
license: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
published: 2026-03-12
updated: 2026-06-04
changes: the article converted to Markdown; the page's comments, side menu and navigation left out
---

# Construct's project format

Construct projects are often saved to a single file with the extension **.c3p** (which stands for "Construct 3 Project"). This file is actually a standard ZIP file with a folder project inside. You can rename a .c3p file to .zip and extract all the files to see the different files and folders that make up your Construct project.

Where supported by the browser, you can also choose to save your project to a folder. This mode skips compressing everything into a ZIP file, and saves all the different files and folders directly in the chosen folder. This is a good option in the following cases:

- Very large projects save faster as a folder project, as Construct only need to update the changed files, rather than compress the entire project every time.
- [Using Construct projects with source control tools like GitHub](https://www.construct.net/en/tutorials/collaborate-construct-2390) requires using a folder-based project, so changes can be tracked in separate files.
- [Using an external code editor](https://www.construct.net/en/make-games/manuals/construct-3/scripting/guides/using-external-editor) to edit JavaScript or TypeScript files in your project.
- Using an AI tool to assist with your project, so it doesn't have to keep decompressing and recompressing a ZIP file with every request.
- Advanced developers writing custom tooling to manipulate Construct projects.

For these purposes it can be useful to have a basic understanding of how the Construct project format works. In particular this can help you understand the kinds of changes you see when using source control tools.

> Both Construct 3 and Construct Animate use the same project format. Where a project uses compatible features, it can be opened in either product.

> Note that the Construct project format does not have any published specification. It is also subject to change over time as Construct is updated. This guide only covers the project format in broad terms that should not change over time. We advise to make changes using the Construct editor where possible. As there is no published specification and the format may change over time, it is difficult for you be sure if any changes made directly to files in a Construct project are valid. In particular some changes involve updating references across a range of files. If a project is manually modified in a way that is invalid, it may become unopenable.

## The main project file

The file named `project.c3proj` is the main project file. It is in JSON format and acts as an index of all the content in the project. It also stores the basic project metadata, such as the name, viewport size, and so on.

The rest of the content in the project is found by looking in the main project file. Any additional files or folders in the project folder are ignored if they are not referenced by the main project file.

The main project file also lists the names of all layouts, event sheets, object types, families, scripts (JavaScript and TypeScript), timelines, flowcharts, 3D models, and additional files like sound and music, in the folder structure in which they appear in the Project Bar.

## Construct content

The content specific to Construct includes the following:

- **Object types**, which define the available object types in the project, such as *PlayerSprite*, saved in the *objectTypes* subfolder
- **Families**, which are essentially groups of object types, saved in the *families* subfolder
- **Layouts**, which consist of layers and arrangements of objects on those layers for purposes like menu and level design, saved in the *layouts* subfolder. The *uistate* sub folder includes JSON files which can be ignored when working with source control.
- **Event sheets**, which consist of Construct's visual blocks that it uses as an alternative to traditional programming languages, saved in the *eventSheets* folder
- **Timelines**, which consist of a sequence of changes over time, such as to control a title screen animation, saved in the *timelines* subfolder
- **Flowcharts**, which consist of a series of connected nodes for purposes like conversation trees and finite state machines, stored in the *flowcharts* subfolder
- **3D models**, saved in the *3dmodels* folder as JSON files. Construct supports importing GLTF (.gltf and .glb) models; these are processed during the import process, and the JSON files saved to the project folder are similar to but not necessarily exactly the same as GLTF files.
- **Color palettes**, saved in the *palettes* folder as JSON files. These are saved to their unique files to allow optionally ignoring them when working with source control.
- **Tilemap brushes**, saved in the *tilemapBrushes* folder as JSON files. These are saved to their unique files to allow optionally ignoring them when working with source control.

These are all saved as JSON files, and the folder structure inside each of their subfolders matches the folder structure listed in project.c3proj (which matches how the user has arranged them in the Project Bar).

The way Construct reads these resources from the project folder works similarly for all these kinds of resources. It first identifies which resources are in the project from the listing in project.c3proj. For each resource, it then reads the corresponding JSON file from the relevant subfolder. The way each resource is read is different, and may involve looking up further resources from the project - notably the images for some objects like Sprite.

### Object images

Objects with images store their images in a special *images* subfolder of the project folder. Construct objects like Tiled Background and 9-patch have a single image, whereas Sprite is able to have multiple images arranged in different animations.

All object images are stored in the *images* subfolder with no further subfolders. Image files are usually stored in PNG format. However in some cases if an image is imported using a lossy format like JPG or AVIF, and the image is not edited inside Construct, then it will be maintained in its original format in the *images* subfolder. The reference to the image in the object type JSON file will indicate its file type (e.g. `"image/avif"`) from which its file extension is determined.

The image file names follow one of two schemes. These names are always lowercased.

- For objects with a single image, the filename is just the name of the object type, e.g. *tiledbackground.png*.
- For objects with animations (Sprite), the filename is in the format `objectname-animationname-framenumber`. The frame number is zero-padded to three digits. For example the image for an object type *Player*'s animation *Default* frame 0 (using a zero-based index) would be *player-default-000.png*.

### Additional information

Here are some additional notes about the way Construct saves JSON data for Construct-specific content.

- Object type JSON files primarily consist of metadata, and the list of animations and animation frames for animated objects (Sprite).
- While the images/animation frames listed in object type JSON files include the image width and height, Construct actually currently ignores this information when loading projects and determines the size from the corresponding image file. This is to facilitate editing images directly in the project folder, outside of Construct, since that can result in a different sized image.
- Layout JSON files primarily consist of metadata, and a tree of layers (as Construct supports sub-layers). Each layer includes metadata and a list of object instances on that layer in Z order.
- Object instances have a "uid", which stands for *Unique ID*. This is an ID shown inside Construct to help refer to specific object instances. Every object instance must have a different UID. There is no requirement for UIDs to be any particular value - they can be incrementing numbers or random numbers. Large random numbers work better when collaborating on projects with source control; Construct usually uses six-digit random numbers in this case to avoid creating inconveniently long numbers that the user might have to reference.
- Event sheet JSON files primarily consist of a tree structure of event blocks (as Construct supports sub-events). There are a variety of different kinds of event blocks, such as the standard event block with conditions and actions, groups, functions, custom actions, and inline script blocks.
- Many kinds of resources have a "sid", which stands for *Serialization ID*. This is an internal ID that helps track resources even if other properties like their name are changed. SIDs should be 15-digit random numbers as that ensures content can be merged without having to adjust SIDs while minimizing the chance of a collision. (SIDs are never shown to the user.)

## Additional project files

Script (JavaScript and TypeScript), sound, music, video, fonts, icons (and splash screens) and general additional files (which appear under the *Files* folder in the Project Bar) store some metadata about the file with their listing in project.c3proj. The files themselves are then stored in the *scripts*, *sounds*, *music*, *videos*, *fonts*, *icons* and *files* subfolders of the project folder respectively. Inside each of these subfolders, there may be further subfolders matching the folder structure specified in project.c3proj (which is as per the way they appear in the Project Bar). Construct then uses these files as-is. For example if an audio file *sfx5.webm* is imported to Construct, the same file *sfx5.webm* will be present in the *sounds* subfolder of the project folder. (It will also be listed in project.c3proj.)

Here are some additional notes about these kinds of files:

- Construct supports both JavaScript (.js) and TypeScript (.ts), and both kinds of files can be in the *scripts* folder. Note that as per our advice in the manual entry [TypeScript in Construct](https://www.construct.net/en/make-games/manuals/construct-3/scripting/using-scripting/typescript-construct), we recommend one of two workflows for TypeScript:
  1. Use only .ts files in the Construct project with no corresponding .js files (relying on Construct's built-in TypeScript support)
  2. Use external .ts files not listed in the Construct project, and using an external tool to compile them to .js. Only those .js files would be listed in the Construct project, so Construct is merely consuming the JavaScript output of the external tool that is compiling TypeScript.
- Sound and music must be in WebM Opus format (with the file extension .webm).
- Construct's [Video plugin](https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/video) supports a variety of video codecs including modern options like AV1, and also supports using both a primary and secondary source. However MP4 with the H.264 codec is generally ubiquitously supported and so a good default choice.
- Fonts should be in WOFF format, as that is the only format consistently supported by browsers.
- Icons (and splash screens) should be in PNG format.
- General files in the *files* subfolder of the project folder can be any kind of file. Construct will not use them itself, but they are available for the project logic to make use of, such as requesting with the AJAX object.

## UI state files

Construct projects contain a variety of files with the extension `.uistate.json`, as well as subfolders with the name *uistate*. These store information about the state of the user interface in the Construct editor. They do not affect the operation of the project in any way. They can all be deleted with no worse effect than parts of Construct's user interface reverting to a default appearance, which the user can then adjust again. Usually it is best for tooling to ignore these files.

Color palettes and tilemap brushes are saved to the folders *tilemapBrushes* and *palettes* respectively in the project folder root. You may or may not want to share these files on source control, so they are stored separately to UI state files.

## Summary

Construct projects consist of a folder with various files and subfolders. This can optionally be compressed in to a ZIP file using the file extension .c3p, but for some purposes it is better to keep the folder as separate files and subfolders. Construct-specific data files are in JSON format. The main project file `project.c3proj` is the key JSON file that contains an index of everything in the project. Most other content in a Construct project consists of industry-standard file formats like PNG and WebM in standalone files.
