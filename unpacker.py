import regex
import click
import os
from progressbar import ProgressBar, Percentage, Bar
from unrar import rarfile
from path import Path

first_part = regex.compile(r"(?V1)(.*)(\.part1|(?<!\.part\d+))\.rar$", regex.I)

@click.command()
@click.argument('path', type=click.Path(exists=True,file_okay=False,resolve_path=True))
@click.option('--recursive', is_flag=True, help='Unpacker will search subdirectories')
@click.option('--clean', is_flag=True, help='Unpacker will delete archives after successful extraction')
#@click.option('--free', type=click.)
def cli(path, recursive, clean):
    '''Unpacker will unpack RAR files in a chosen directory and 
        optionally delete them after successful extraction.

        Unpacker will only process the first valid RAR file 
        found in a directory. It can handle multi-part archives
        in both forms (.partX.rar and .rXX)'''

    click.echo("Recursive = %s" % recursive)
    click.echo("Cleaning = %s" % clean)

    archives = find_archives(path, recursive)

    for archive in archives:
        click.echo("Extracting file %s" % archive.abspath)
        archive.unpack(clean)

    click.echo("All Done!")

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
        #click.echo("File %s is RAR archive" % filepath)
        if first_part.search(filepath):
            #click.echo("And should be first archive")
            return True
    return False

class Archive(object):
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

        return parts

    def get_total_size(self):
        total_size = 0
        rar = rarfile.RarFile(self.abspath)

        previous_entry = u""
        for rarinfo in rar.infolist():
            # filelist was generated with mode RAR_OM_LIST_INCSPLIT
            # which means spanning files get two entries.
            if previous_entry == rarinfo.filename:
                continue
            #click.echo("Found archived file %s " % rarinfo.filename)
            total_size += rarinfo.file_size
            previous_entry = rarinfo.filename

        click.echo("Total size = %dkB" % (int(total_size) / 1000))

        return total_size

    def unpack(self, clean=False, destination=None):
        if (destination == None):
            destination = self.dirpath

        callback = ProgressCallback(self.get_total_size())

        try:
            rar = rarfile.RarFile(self.abspath)
            rar.extractall(destination, callback=callback._callback)
        except rarfile.BadRarFile:
            click.echo("Failed to extract %s" % self.abspath)
            return

        click.echo("Done!")

        if clean:
            click.echo("Removing RAR file(s):")
            for file in self.parts:
                click.echo(file)
                os.remove(file)
            # Make sure first part is deleted
            click.echo(self.abspath)
            os.remove(self.abspath)

    def delete(self):
        return False

class ProgressCallback(object):
    def __init__(self, total_size):
        self._total_size = total_size
        self._read_size = 0
        self._bar = ProgressBar(widgets=[Percentage(), Bar()], maxval=total_size).start()

    def _callback(self, msg, user_data, p1, p2):
        if msg == constants.UCM_PROCESSDATA:
            self._read_size += p2
            self._bar.update(self._read_size)
            if self._read_size >= self._total_size:
                self._bar.finish()
        return 1

