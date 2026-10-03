#!/usr/bin/env python3
"""madeira-bcd: env.MADEIRA_SC_REG_RO=1 -- Social Club's registry key read-only.

On the owner's Windows 11 PC (2026-10-03, same Steam build of GTA V Enhanced,
-nobattleye -scOfflineOnly) socialclub.dll opens
HKLM\\Software\\WOW6432Node\\Rockstar Games\\Rockstar Games Social Club\\ for
writing and Windows answers ACCESS DENIED (the game is not elevated). Its
socialclub.log then says "Fatal Error: code 1024", "Social Club UI - Entering
State: 'WAIT_BROWSER'", times out after ~31 s ('FAILED') and the game goes on to
Story mode without the overlay. Wine has no UAC, so on the device the same open
succeeds, Social Club fully initialises ("SDK fully initialized") and the game
waits for a browser that never becomes ready. With MADEIRA_SC_REG_RO=1,
NtCreateKey / NtOpenKeyEx refuse write access (STATUS_ACCESS_DENIED) to any key
whose name contains "Rockstar Games Social Club", as a non-admin Windows does;
read-only opens are unchanged.

Applied to wine/dlls/ntdll/unix/registry.c in the CI checkout; the submodule is
not committed to. Idempotent; exits non-zero when an anchor is missing.
Usage: patch-wine-sc-registry.py [path/to/wine/dlls/ntdll/unix/registry.c]
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "wine/dlls/ntdll/unix/registry.c"
src = open(path).read()
marker = "madeira-bcd: [sc-reg]"
if marker in src:
    print("patch-wine-sc-registry: already patched")
    sys.exit(0)

helper = r'''#ifdef WINE_IOS
#include <stdio.h>
#include <stdlib.h>
/* madeira-bcd: [sc-reg] (tools/patch-wine-sc-registry.py, MADEIRA_SC_REG_RO=1). */
static int madeira_sc_reg_ro( const UNICODE_STRING *name, ACCESS_MASK access )
{
    static const char tag[] = "rockstar games social club";
    static int on = -1, said;
    const ACCESS_MASK write = KEY_SET_VALUE | KEY_CREATE_SUB_KEY | KEY_CREATE_LINK | DELETE | WRITE_DAC |
                              WRITE_OWNER | GENERIC_WRITE | GENERIC_ALL | MAXIMUM_ALLOWED;
    unsigned int n, i, k;

    if (on < 0)
    {
        const char *e = getenv( "MADEIRA_SC_REG_RO" );
        on = e && e[0] == '1';
    }
    if (!on || !(access & write) || !name || !name->Buffer) return 0;
    n = name->Length / sizeof(WCHAR);
    for (i = 0; i + sizeof(tag) - 1 <= n; i++)
    {
        for (k = 0; tag[k]; k++)
        {
            WCHAR c = name->Buffer[i + k];
            if (c >= 'A' && c <= 'Z') c += 32;
            if (c != (WCHAR)tag[k]) break;
        }
        if (tag[k]) continue;
        if (said++ < 16)
            fprintf( stderr, "[sc-reg] MADEIRA_SC_REG_RO: write access 0x%08x to %s refused (STATUS_ACCESS_DENIED), "
                     "as on a non-admin Windows\n", (unsigned int)access, debugstr_us( name ) );
        return 1;
    }
    return 0;
}
#endif

'''

anchor_create = "NTSTATUS WINAPI NtCreateKey( HANDLE *key, ACCESS_MASK access, const OBJECT_ATTRIBUTES *attr,"
if src.count(anchor_create) != 1:
    sys.exit("patch-wine-sc-registry: NtCreateKey anchor not found")
i = src.index(anchor_create)
line_start = src.rfind("\n/***", 0, i)
ins = line_start + 1 if line_start >= 0 else i
src = src[:ins] + helper + src[ins:]

create_old = '''    if (!attr->ObjectName->Length && !attr->RootDirectory) return STATUS_OBJECT_PATH_SYNTAX_BAD;
    if ((ret = alloc_object_attributes( attr, &objattr, &len ))) return ret;'''
create_new = '''    if (!attr->ObjectName->Length && !attr->RootDirectory) return STATUS_OBJECT_PATH_SYNTAX_BAD;
#ifdef WINE_IOS
    if (madeira_sc_reg_ro( attr->ObjectName, access )) return STATUS_ACCESS_DENIED;
#endif
    if ((ret = alloc_object_attributes( attr, &objattr, &len ))) return ret;'''
if src.count(create_old) != 1:
    sys.exit("patch-wine-sc-registry: NtCreateKey body anchor not found")
src = src.replace(create_old, create_new)

open_old = '''    if (attr->ObjectName->Length & 1) return STATUS_OBJECT_NAME_INVALID;

    TRACE( "(%p,%s,%x,%p)\\n", attr->RootDirectory, debugstr_us(attr->ObjectName), access, key );'''
open_new = '''    if (attr->ObjectName->Length & 1) return STATUS_OBJECT_NAME_INVALID;
#ifdef WINE_IOS
    if (madeira_sc_reg_ro( attr->ObjectName, access )) return STATUS_ACCESS_DENIED;
#endif

    TRACE( "(%p,%s,%x,%p)\\n", attr->RootDirectory, debugstr_us(attr->ObjectName), access, key );'''
if src.count(open_old) != 1:
    sys.exit("patch-wine-sc-registry: NtOpenKeyEx body anchor not found")
src = src.replace(open_old, open_new)

open(path, "w").write(src)
print("patch-wine-sc-registry: [sc-reg] write access to Social Club's key refused in NtCreateKey / NtOpenKeyEx "
      "(MADEIRA_SC_REG_RO=1)")
