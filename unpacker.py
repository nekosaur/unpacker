import regex
import click
import os
import psutil
from progressbar import ProgressBar, Percentage, Bar
from unrar import rarfile
from unrar import constants
from unipath import Path, DIRS, FILES

first_part = regex.compile(r"(?V1)(.*)(\.part0{0,2}1|(?<!\.part\d+))\.rar$", regex.I)
base = 1024
size_dict = {"K":base, "M":base*base, "G":base*base*base}

@click.command()
@click.argument('path', type=click.Path(exists=True,file_okay=False,resolve_path=True))
@click.option('--top', is_flag=True, help='Unpacker will treat PATH as top dir, go through one level of child folders')
@click.option('--clean', is_flag=True, help='Unpacker will delete archives after successful extraction')
@click.option('--buffer', default="4000M", help='Unpacker will not extract any file that will result in free space dropping below the specified buffer')
#@click.option('--free', type=click.)
def cli(path, top, clean, buffer):
    '''Unpacker will unpack RAR files in a chosen directory and 
        optionally delete them after successful extraction.

        Unpacker will only process the first valid RAR file 
        found in a directory. It can handle multi-part archives
        in both forms (.partX.rar and .rXX)'''

    click.echo("Path = %s" % path)
    click.echo("Top = %s" % top)
    click.echo("Clean = %s" % clean)
    click.echo("Buffer = %s" % buffer)

    dir = Path(path)

    if top:
        for item in dir.listdir(filter=DIRS):
            click.echo(item)
            process_dir(item, clean, buffer)
    else:
        click.echo(dir)
        process_dir(dir, clean, buffer)

    click.echo("All Done!")

def process_dir(dir, clean, buffer):
    click.echo("Parsing directory %s" % dir)

    archive = find_archive(dir)

    if archive:
        click.echo("Extracting file %s" % archive.abspath)
        archive.unpack(clean, get_bytes(buffer))


def find_archive(dir):
    
    for item in dir.listdir(pattern='*.rar', filter=FILES):
        if is_first_archive(item.resolve()):
            return Archive(item)

    return None

def is_first_archive(filepath):
    if rarfile.is_rarfile(filepath):
        #click.echo("File %s is RAR archive" % filepath)
        if first_part.search(filepath):
            #click.echo("And should be first archive")
            return True
    return False

def get_bytes(size):
    '''converts a human readable size string (2M, 4G, etc) to bytes'''
    postfix = size[-1:]
    size = size[:-1]
    mult = size_dict.get(postfix)
    return int(size) * size_dict.get(postfix)

def get_human(size, postfix):
    div = size_dict.get(postfix)
    return size / div

class Archive(object):
    def __init__(self, file):
        click.echo("Creating Archive %s" % file.absolute())
        self.abspath = file.absolute()
        self.dirpath = file.parent
        self.filename = file.stem

        self.parts = self.get_parts()

    def get_parts(self):
        multi_part = regex.compile("(?V1)" + self.filename + "(\.part[\d]+\.rar|\.r[\d]{2})$", regex.I)
        parts = []
        directory = Path(self.dirpath)

        for item in directory.listdir(pattern='*.r*', filter=FILES):
            filepath = item.absolute()
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

    def unpack(self, clean=False, space_buffer=None):
        #if (destination == None):
        #    destination = self.dirpath
        destination = self.dirpath

        # Check for enough free space
        total_size = self.get_total_size()
        free_space = psutil.disk_usage(self.dirpath).free
        if (free_space - total_size < space_buffer):
            click.echo("Unpacking this file would only leave %d MB free space. Skipping.." % get_human(free_space - total_size, "M"))
            return

        try:
            rar = rarfile.RarFile(self.abspath)
            callback = ProgressCallback(total_size)
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

