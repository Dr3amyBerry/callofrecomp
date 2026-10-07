#ifndef CODRECOMP_HOST_SERVICES_H
#define CODRECOMP_HOST_SERVICES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Portable host-side services for a future reconstructed SP engine.
 *
 * THIS IS NOT THE ORIGINAL CoD 1.5 game-module calling convention.
 * The observed gamex86.dll callback transports 32-bit words. The adapter
 * that bridges the legacy syscall table to these services must decode/validate
 * pointers, handles, modes and return values explicitly.
 *
 * Native Android ARM64 pointers MUST remain native pointers at this boundary;
 * never truncate them to cod_vm_word32_t.
 */

/* Logical engine-managed file handle, NOT a native OS file descriptor. */
typedef uint32_t cod_host_fs_handle_t;

typedef struct cod_host_services_s {
    /* Passed unmodified to every callback; may be NULL. */
    void *context;

    /*
     * All mode, timing and pathname policies are implementation-defined
     * until filesystem behavior is independently recovered.
     */
    int32_t (*fs_open)(void *context, const char *path,
                       cod_host_fs_handle_t *out_handle, int32_t mode);

    /*
     * Native read/write callbacks return byte counts or negative errors.
     * The reconstructed engine dispatcher may deliberately discard a result
     * to emulate the legacy SP syscall behavior (e.g. FS_READ returns EAX=0).
     */
    ptrdiff_t (*fs_read)(void *context, void *buffer, size_t requested_bytes,
                         cod_host_fs_handle_t handle);
    ptrdiff_t (*fs_write)(void *context, const void *buffer, size_t requested_bytes,
                          cod_host_fs_handle_t handle);

    void (*fs_close)(void *context, cod_host_fs_handle_t handle);

    int32_t (*fs_rename)(void *context, const char *old_path,
                         const char *new_path);

    /*
     * A 1.5 SP-style file-list adapter. The precise encoding/order of
     * filenames inside output_buffer remains to be verified before use.
     */
    int32_t (*fs_getfilelist)(void *context, const char *directory,
                              const char *extension, char *output_buffer,
                              size_t buffer_bytes);

    /* exec_when numeric semantics are not hard-coded here. */
    void (*execute_console_text)(void *context, int32_t exec_when,
                                  const char *text);
} cod_host_services_t;

#ifdef __cplusplus
}
#endif

#endif /* CODRECOMP_HOST_SERVICES_H */
