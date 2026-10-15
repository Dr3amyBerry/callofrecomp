#pragma once
#include "x87_native_state.h"
#include <stddef.h>
#include <stdatomic.h>

typedef struct {
    uintptr_t native_pc;
    uint32_t guest_pc;
    uint16_t opcode;
} native_x87_instruction;
typedef struct {
    x87_native_state initial;
    uintptr_t memory_base;
    const native_x87_instruction *instructions;
    size_t count;
    uint16_t code_selector,data_selector;
} native_x87_context;

// The existing runtime has one guest thread and global R/PC. A region publishes
// its live stack context only around the indivisible native asm block. Other
// host threads cannot match its instruction addresses and are not attributed.
extern const native_x87_context *volatile native_x87_active;
int codsp_native_x87_region_try(uint8_t *,uint8_t *,uint32_t *,uint16_t,uint16_t);

static inline const native_x87_instruction *native_x87_find(
        const native_x87_context *context,uintptr_t pc) {
    for(size_t i=0;i<context->count;i++)
        if(context->instructions[i].native_pc==pc) return context->instructions+i;
    return NULL;
}

// No allocation, logging or guest memory access. Native addresses must be
// disjoint from 32-bit imported metadata (the region enforces a high mapping).
// Unknown instruction/FPU metadata fails without changing either output.
static inline int native_x87_decode_fault(const native_x87_context *context,
        uintptr_t native_pc,const uint8_t *image,x87_native_state *output,
        uint32_t *guest_pc) {
    const native_x87_instruction *fault=native_x87_find(context,native_pc);
    if(!fault) return 0;
    x87_native_state result=context->initial;
    uint64_t ip,dp;uint32_t initial_ip,initial_dp;
    memcpy(&ip,image+8,8);memcpy(&dp,image+16,8);
    memcpy(&initial_ip,result.bytes+12,4);memcpy(&initial_dp,result.bytes+20,4);
    const native_x87_instruction *last=native_x87_find(context,(uintptr_t)ip);
    if(last) {
        memcpy(result.bytes+12,&last->guest_pc,4);
        memcpy(result.bytes+18,&last->opcode,2);
        memcpy(result.bytes+16,&context->code_selector,2);
    } else if(ip!=initial_ip) return 0;
    if(dp>=context->memory_base && dp-context->memory_base<(UINT64_C(1)<<32)) {
        uint32_t address=(uint32_t)(dp-context->memory_base);
        memcpy(result.bytes+20,&address,4);
        memcpy(result.bytes+24,&context->data_selector,2);
    } else if(dp!=initial_dp) return 0;
    x87_native_state_read_fxsave64_arithmetic(&result,image);
    *output=result;*guest_pc=fault->guest_pc;return 1;
}

// Publish complete FPU state and RET PC BEFORE reading the guest return slot.
// A fault leaves ESP and the return scratch unchanged. The compiler fence is
// required because ordinary C loads may otherwise move before the checkpoint.
static inline void native_x87_finish_return(uint8_t *regs,uint8_t *memory,
        const x87_native_state *state,uint32_t esp,uint32_t ret_pc,uint32_t *pc) {
    x87_native_state_to_registers(regs,state);
    *pc=ret_pc;
    atomic_signal_fence(memory_order_seq_cst);
    uint32_t target;memcpy(&target,memory+esp,4);
    atomic_signal_fence(memory_order_seq_cst);
    memcpy(regs+0x284,&target,4);esp+=4;memcpy(regs+0x10,&esp,4);*pc=target;
}
