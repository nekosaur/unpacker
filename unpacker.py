import regex
import click
import os
import ctypes
from path import Path
from unrar import rarfile
from unrar import unrarlib
from unrar import constants

#pattern = regex.compile('(?V1)(?<!part[\d]+)\.rar')
first_part = regex.compile(r"(?V1)(.*)(\.part1|(?<!\.part\d+))\.rar$", regex.I)
#pattern = regex.compile(r"(?V1)(?:part1\.rar|\.rar)")
#(?:part(\d{1,}))?\.(?:r(\d{2})|rar)$

@click.command()
@click.argument('path', type=click.Path(exists=True,file_okay=False,resolve_path=True))
@click.option('--recursive', is_flag=True, help='Makes unpacker look in subdirectories')
@click.option('--clean', is_flag=True, help='Unpacker will delete archives after successful extraction')
def cli(path, recursive, clean):
    '''Unpacker will unpack RAR files in a chosen directory and 
        optionally delete them after successful extraction.

        Unpacker will only process the first valid RAR file 
        found in a directory. It can handle multi-part archives
        in both forms (.partX.rar and .rXX)'''
    click.echo(path)
    click.echo(recursive)
    click.echo(clean)

    archives = find_archives(path, recursive)

    #for archive in archives:
    #   unpack_archive(archive)
    #   if (clean):
    #       delete_archive(archive)

    #with click.progressbar(length=1000000) as test:
    #    while not test.finished:
    #        test.next(100)

    #return

    for archive in archives:
        click.echo(archive.abspath)
        archive.unpack(clean)

def do(x):
    return False

def find_archives(path, recursive):
    archives = []
    directory = Path(path)

    click.echo("Parsing directory %s" % directory)
    for item in directory.files('*.rar'):
        if item.isfile() and is_first_archive(item.abspath()):
            archives.extend([Archive(item)])
            break

    if recursive:
        for folder in directory.dirs():
            archives.extend(find_archives(folder, recursive))

    return archives

def is_first_archive(filepath):
    if rarfile.is_rarfile(filepath):
        click.echo("File %s is RAR archive" % filepath)
        if first_part.search(filepath):
            click.echo("And should be first archive")
            return True
    return False

class Archive:
    def __init__(self, file):
        click.echo("Creating Archive %s" % file.abspath())
        self.abspath = file.abspath()
        self.dirpath = file.dirname()
        self.filename = first_part.search(file.basename()).group(1)

        self.parts = self.get_parts()

    def get_parts(self):
        multi_part = regex.compile("(?V1)" + self.filename + "(\.part[\d]+\.rar|\.r[\d]{2})$", regex.I)
        parts = []
        directory = Path(self.dirpath)

        for item in directory.walkfiles('*.r*'):
            filepath = item.abspath()
            if rarfile.is_rarfile(filepath):
                if multi_part.search(filepath):
                    parts.append(item)
                    click.echo("File %s added to parts" % item.abspath())

        return parts

    def callback(self, msg, user_data, p1, p2):
        if msg == constants.UCM_PROCESSDATA:
            click.echo(p2)
        return 1

    def _open(self, archive):
        """Open RAR archive file."""
        try:
            handle = unrarlib.RAROpenArchiveEx(ctypes.byref(archive))
        except unrarlib.UnrarException:
            raise BadRarFile("Invalid RAR file.")
        return handle
        
    def _close(self, handle):
        """Close RAR archive file."""
        try:
            unrarlib.RARCloseArchive(handle)
        except unrarlib.UnrarException:
            raise BadRarFile("RAR archive close error.")

    def _read_header(self, handle):
        """Read current member header into a RarInfo object."""
        rarinfo = None
        header_data = unrarlib.RARHeaderDataEx()
        res = unrarlib.RARReadHeaderEx(handle, ctypes.byref(header_data))
        if res != constants.ERAR_END_ARCHIVE:
            rarinfo = rarfile.RarInfo(header=header_data)
        return rarinfo

    def _process_current(self, handle, op, dest_path=None, dest_name=None):
        """Process current member with 'op' operation."""
        unrarlib.RARProcessFileW(handle, op, dest_path, dest_name)

    def get_total_size(self):
        total_size = 0
        archive = unrarlib.RAROpenArchiveDataEx(
            self.abspath, mode=constants.RAR_OM_EXTRACT)
        handle = self._open(archive)

        click.echo("Getting total size")

        try:
            rarinfo = self._read_header(handle)
            while rarinfo is not None:
                total_size += rarinfo.file_size
                rarinfo = self._read_header(handle)
        except unrarlib.UnrarException:
            raise BadRarFile("Bad RAR archive data.")
        finally:
            self._close(handle)

        click.echo("Total size = %dkB" % (int(total_size) / 1000))
        return total_size

    def unpack(self, clean=False, destination=None):
        # TODO: Check for free space
        if (destination == None):
            destination = self.dirpath

        callback = ProgressCallback(self.get_total_size())
        c_callback = unrarlib.UNRARCALLBACK(callback._callback)

        archive = unrarlib.RAROpenArchiveDataEx(
            self.abspath, mode=constants.RAR_OM_EXTRACT)
        handle = self._open(archive)
        
        unrarlib.RARSetCallback(handle, c_callback, 0)
        
        try:
            rarinfo = self._read_header(handle)
            with click.progressbar(length=callback._total_size) as callback._bar:
                while rarinfo is not None:
                    self._process_current(
                        handle, constants.RAR_EXTRACT, destination)
                    rarinfo = self._read_header(handle)
        except unrarlib.UnrarException:
            raise BadRarFile("Bad RAR archive data.")
        finally:
            self._close(handle)

        if clean:
            click.echo("Removing RAR file(s)")
            for file in self.parts:
                click.echo(file)
                os.remove(file)
            # Make sure first part is deleted
            os.remove(self.abspath)

    def delete(self):
        return False

class ProgressCallback(object):
    def __init__(self, total_size):
        self._total_size = total_size
        self._bar = None

    def _callback(self, msg, user_data, p1, p2):
        if msg == constants.UCM_PROCESSDATA:
            self._bar.next(p2)
        return 1
