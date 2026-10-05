#!/usr/bin/env python3
"""Check the virtual disk's Windows packets and rejection paths on a POSIX host.

Uses the pinned Wine headers and production responder, including short,
unaligned and oversized buffers. Also compile the actual server adapter
against the real server object/fd interfaces, without an iOS SDK.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
test = r'''
#include <assert.h>
#include <stdio.h>
#include <sys/statvfs.h>
#include "storage_device_ios.h"

static struct madeira_disk_info disk = { 512ULL * 1024 * 1024 * 1024 };
static unsigned char buffer[256];
static size_t written;

static unsigned int request(unsigned int code, const void *in, size_t in_size, size_t out_size)
{
    memset(buffer, 0xa5, sizeof(buffer));
    written = SIZE_MAX;
    unsigned int status = madeira_disk_ioctl(&disk, code, in, in_size,
                                              buffer + 17, out_size, &written);
    assert(written <= out_size);
    for (size_t i = 0; i < 17; i++) assert(buffer[i] == 0xa5);
    for (size_t i = 17 + written; i < sizeof(buffer); i++) assert(buffer[i] == 0xa5);
    return status;
}
static void fixed_reply(unsigned int code, const unsigned char *expected, size_t size)
{
    for (size_t len = 0; len < size; len++)
    {
        assert(request(code, NULL, 0, len) == (unsigned int)STATUS_BUFFER_TOO_SMALL);
        assert(!written);
    }
    assert(request(code, NULL, 0, size) == (unsigned int)STATUS_SUCCESS);
    assert(written == size && !memcmp(buffer + 17, expected, size));
    assert(request(code, NULL, 0, 128) == (unsigned int)STATUS_SUCCESS);
    assert(written == size && !memcmp(buffer + 17, expected, size));
}
int main(void)
{
    _Static_assert(sizeof(STORAGE_DEVICE_NUMBER) == 12, "Windows device number ABI");
    _Static_assert(sizeof(DISK_GEOMETRY) == 24, "Windows geometry ABI");
    _Static_assert(sizeof(DISK_GEOMETRY_EX) == 40, "Windows extended geometry ABI");
    _Static_assert(sizeof(STORAGE_DESCRIPTOR_HEADER) == 8, "Windows descriptor header ABI");
    _Static_assert(sizeof(STORAGE_PROPERTY_QUERY) == 12, "Windows property query ABI");
    _Static_assert(offsetof(STORAGE_DEVICE_DESCRIPTOR, SerialNumberOffset) == 24, "Windows serial offset ABI");
    _Static_assert(sizeof(STORAGE_DEVICE_DESCRIPTOR) == 40, "Windows device descriptor ABI");

    assert(madeira_disk_capacity(0, 4096) == 0);
    assert(madeira_disk_capacity(UINT64_MAX, 4096) == 0);
    assert(madeira_disk_capacity(INT64_MAX, 2) == 0);
    assert(madeira_disk_capacity(INT64_MAX, 1) == INT64_MAX);
    assert(madeira_disk_capacity(1048576, 4096) == 4294967296ULL);
    struct statvfs fs;
    assert(!statvfs(".", &fs));
    uint64_t actual = madeira_disk_capacity(fs.f_blocks, fs.f_frsize ? fs.f_frsize : fs.f_bsize);
    assert(actual > 0 && actual <= INT64_MAX);

    /* Serialized device identity is a virtual disk, index0/whole disk. */
    static const unsigned char number[12] = {7,0,0,0, 0,0,0,0, 0,0,0,0};
    fixed_reply(IOCTL_STORAGE_GET_DEVICE_NUMBER, number, sizeof(number));
    unsigned char length[8] = {0};
    uint64_t bytes = disk.bytes;
    memcpy(length, &bytes, sizeof(bytes));
    fixed_reply(IOCTL_DISK_GET_LENGTH_INFO, length, sizeof(length));

    for (size_t len = 0; len < 24; len++)
        assert(request(IOCTL_DISK_GET_DRIVE_GEOMETRY, NULL, 0, len) == (unsigned int)STATUS_BUFFER_TOO_SMALL);
    assert(!request(IOCTL_DISK_GET_DRIVE_GEOMETRY, NULL, 0, 128));
    DISK_GEOMETRY geometry;
    memcpy(&geometry, buffer + 17, sizeof(geometry));
    assert(written == 24 && geometry.MediaType == FixedMedia && geometry.BytesPerSector == 512);
    assert(geometry.TracksPerCylinder == 255 && geometry.SectorsPerTrack == 63);
    assert((uint64_t)geometry.Cylinders.QuadPart * 255 * 63 * 512 <= disk.bytes);
    for (size_t len = 0; len < 40; len++)
        assert(request(IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, NULL, 0, len) == (unsigned int)STATUS_BUFFER_TOO_SMALL);
    assert(!request(IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, NULL, 0, 128));
    DISK_GEOMETRY_EX extended;
    memcpy(&extended, buffer + 17, sizeof(extended));
    assert(written == 40 && (uint64_t)extended.DiskSize.QuadPart == disk.bytes);
    assert(!memcmp(&geometry, &extended.Geometry, sizeof(geometry)));

    STORAGE_PROPERTY_QUERY query = { StorageDeviceProperty, PropertyStandardQuery, {0} };
    for (size_t len = 0; len < sizeof(query); len++)
        assert(request(IOCTL_STORAGE_QUERY_PROPERTY, &query, len, 128) == (unsigned int)STATUS_INVALID_PARAMETER);
    assert(request(IOCTL_STORAGE_QUERY_PROPERTY, NULL, sizeof(query), 128) == (unsigned int)STATUS_INVALID_PARAMETER);
    for (size_t len = 0; len < 8; len++)
        assert(request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), len) == (unsigned int)STATUS_BUFFER_TOO_SMALL);
    assert(!request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), 8));
    STORAGE_DESCRIPTOR_HEADER header;
    memcpy(&header, buffer + 17, sizeof(header));
    assert(written == 8 && header.Version == 40 && header.Size == 61);
    for (size_t len = 8; len < header.Size; len++)
    {
        assert(!request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), len));
        assert(written == 8);
    }
    /* A misaligned request must be copied, never dereferenced as a struct. */
    unsigned char input[sizeof(query) + 1];
    memcpy(input + 1, &query, sizeof(query));
    assert(!request(IOCTL_STORAGE_QUERY_PROPERTY, input + 1, sizeof(query), header.Size));
    STORAGE_DEVICE_DESCRIPTOR descriptor;
    memcpy(&descriptor, buffer + 17, sizeof(descriptor));
    assert(written == header.Size && descriptor.BusType == BusTypeVirtual);
    assert(descriptor.DeviceType == 0 && !descriptor.RemovableMedia);
    assert(!descriptor.SerialNumberOffset && !descriptor.VendorIdOffset && !descriptor.ProductRevisionOffset);
    assert(descriptor.ProductIdOffset == 40);
    assert(!strcmp((char *)buffer + 17 + descriptor.ProductIdOffset, "Madeira virtual disk"));

    query.QueryType = PropertyExistsQuery;
    assert(!request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), 0) && !written);
    query.QueryType = PropertyMaskQuery;
    assert(request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), 128) == (unsigned int)STATUS_NOT_SUPPORTED);
    query.QueryType = PropertyStandardQuery;
    query.PropertyId = StorageDeviceSeekPenaltyProperty;
    assert(request(IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), 128) == (unsigned int)STATUS_NOT_SUPPORTED);
    assert(request(IOCTL_DISK_SET_DRIVE_LAYOUT, NULL, 0, 128) == (unsigned int)STATUS_NOT_SUPPORTED);
    assert(request(0xffffffff, NULL, 0, 128) == (unsigned int)STATUS_NOT_SUPPORTED);
    disk.bytes = 0;
    assert(request(IOCTL_DISK_GET_LENGTH_INFO, NULL, 0, 128) == (unsigned int)STATUS_DEVICE_NOT_READY);
    disk.bytes = UINT64_MAX;
    assert(request(IOCTL_DISK_GET_LENGTH_INFO, NULL, 0, 128) == (unsigned int)STATUS_DEVICE_NOT_READY);
    puts("PASS: virtual disk Windows ABI, real filesystem capacity, bounded and unaligned replies, unsupported requests");
}
'''

with tempfile.TemporaryDirectory(prefix='madeira-storage-device-') as tmp:
    tmp = Path(tmp)
    (tmp / 'config.h').write_text('#define _GNU_SOURCE 1\n')
    source = tmp / 'check.c'
    source.write_text(test)
    flags = ['-std=gnu11', '-D__WINESRC__', '-DWINE_UNIX_LIB', '-Wall', '-Wextra', '-Werror',
             '-Wno-unused-parameter', '-I', str(tmp), '-I', str(root / 'wine/include'),
             '-I', str(root / 'wine/server'), '-I', str(root / 'build/wineserver')]
    cc = os.environ.get('CC', 'cc')
    subprocess.run([cc, *flags, '-fsyntax-only', str(root / 'build/wineserver/storage_device_ios.c')], check=True)
    binary = tmp / 'check'
    subprocess.run([cc, *flags, '-O1', '-g', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: production wineserver adapter compiles against the pinned object/fd interfaces')
