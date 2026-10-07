#include <assert.h>
#include <stdint.h>

#include "codrecomp/game_sp_syscalls.h"
#include "codrecomp/vm_abi.h"

int main(void) {
    const float source = 123.25f;
    const cod_vm_word32_t encoded = cod_vm_float_to_word(source);
    const float decoded = cod_vm_word_to_float(encoded);

    assert(sizeof(cod_vm_word32_t) == 4);
    assert(sizeof(cod_vm_call32_t) == (1u + COD_VM_MAX_ARGS) * 4u);
    assert(decoded == source);

    assert(COD_SP_G_PRINT == 0);
    assert(COD_SP_G_ENDGAME == 3);
    assert(COD_SP_G_MILLISECONDS == 4);
    assert(COD_SP_G_HUNK_FREE_TEMP == 19);
    assert(COD_SP_G_FS_FOPEN_FILE == 21);
    assert(COD_SP_G_FS_READ == 22);
    assert(COD_SP_G_FS_WRITE == 23);
    assert(COD_SP_G_FS_RENAME == 36);
    assert(COD_SP_G_FS_FCLOSE_FILE == 37);
    assert(COD_SP_G_FS_GETFILELIST == 40);
    assert(COD_SP_G_SEND_CONSOLE_COMMAND == 41);
    assert(COD_SP_G_DISPATCH_MAX == 211);

    return 0;
}
