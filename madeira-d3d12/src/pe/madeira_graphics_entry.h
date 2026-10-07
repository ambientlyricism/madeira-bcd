#ifndef MADEIRA_GRAPHICS_ENTRY_H
#define MADEIRA_GRAPHICS_ENTRY_H

/* A native COM address cannot be patched with x64 instructions. Let clang/lld
 * emit the ARM64EC fast-forward entry and its ABI thunks, rather than building
 * an untyped jump or copying guest instructions into native .text. External
 * linkage is required: clang ignores hybrid_patchable on static functions. */
#if defined(__arm64ec__)
# if !__has_attribute(hybrid_patchable)
#  error "The ARM64EC toolchain must support hybrid_patchable"
# endif
# define MAD_X64_GRAPHICS_ENTRY __attribute__((hybrid_patchable, noinline))
#else
# define MAD_X64_GRAPHICS_ENTRY
#endif

/* Per-process opt-in. Preserve LastError even during factory/DLL startup. */
static inline int mad_x64_graphics_entry_enabled(void) {
    char value[2];
    DWORD saved_error = GetLastError();
    DWORD n = GetEnvironmentVariableA("MADEIRA_X64_GRAPHICS_ENTRY", value, sizeof value);
    int enabled = n == 1 && value[0] == '1';
    SetLastError(saved_error);
    return enabled;
}

#endif
