#ifndef CODRECOMP_GAME_SP_SYSCALLS_H
#define CODRECOMP_GAME_SP_SYSCALLS_H

/*
 * Evidence-backed prefix of the Call of Duty 1.5 single-player game-module
 * syscall ABI. Values after 19 remain intentionally unnamed until independently
 * verified against the supplied SP executable.
 */
typedef enum cod_sp_game_syscall_e {
    COD_SP_G_PRINT = 0,
    COD_SP_G_ERROR = 1,
    COD_SP_G_ERROR_NOPREFIX = 2,
    COD_SP_G_ENDGAME = 3,
    COD_SP_G_MILLISECONDS = 4,
    COD_SP_G_CVAR_REGISTER = 5,
    COD_SP_G_CVAR_UPDATE = 6,
    COD_SP_G_CVAR_SET = 7,
    COD_SP_G_CVAR_SETVAR = 8,
    COD_SP_G_CVAR_VARIABLE_INTEGER_VALUE = 9,
    COD_SP_G_CVAR_VARIABLE_VALUE = 10,
    COD_SP_G_CVAR_VARIABLE_STRING_BUFFER = 11,
    COD_SP_G_ARGC = 12,
    COD_SP_G_ARGV = 13,
    COD_SP_G_HUNK_ALLOC = 14,
    COD_SP_G_HUNK_ALLOC_LOW = 15,
    COD_SP_G_HUNK_ALLOC_ALIGN = 16,
    COD_SP_G_HUNK_ALLOC_LOW_ALIGN = 17,
    COD_SP_G_HUNK_ALLOC_TEMP = 18,
    COD_SP_G_HUNK_FREE_TEMP = 19,

    COD_SP_G_KNOWN_PREFIX_MAX = 19,
    COD_SP_G_DISPATCH_MAX = 211
} cod_sp_game_syscall_t;

#endif /* CODRECOMP_GAME_SP_SYSCALLS_H */
