#include "recomp_rt.h"
#include <stdio.h>
#include <stdint.h>

static uint64_t next(uint64_t *state) {
    uint64_t x=*state;
    x ^= x<<13; x ^= x>>7; x ^= x<<17;
    return *state=x;
}
static int ref_add(u128 x, u128 y, int n) {
    if(n==16) {
        s128 out;
        return __builtin_add_overflow((s128)x,(s128)y,&out);
    }
    s128 a=sx(mask(x,n),n), b=sx(mask(y,n),n), sum=a+b;
    return sx(mask((u128)sum,n),n)!=sum;
}
static int ref_sub(u128 x, u128 y, int n) {
    if(n==16) {
        s128 out;
        return __builtin_sub_overflow((s128)x,(s128)y,&out);
    }
    s128 a=sx(mask(x,n),n), b=sx(mask(y,n),n), dif=a-b;
    return sx(mask((u128)dif,n),n)!=dif;
}
static s128 ref_signed_extend(u128 v, int n) {
    const u128 bits=mask(v,n);
    if(n==16) return (s128)bits;
    const u128 sign=(u128)1<<(8*n-1);
    // Mathematical two's-complement interpretation in a wider integer:
    // the subtraction stays within signed __int128 for n <= 15.
    return (s128)bits - ((bits & sign) ? (s128)(sign << 1) : 0);
}
static int check(u128 a,u128 b,int n) {
    if(sx(a,n)!=ref_signed_extend(a,n) || sx(b,n)!=ref_signed_extend(b,n)){
        fprintf(stderr,"sign-extension mismatch for width %d\\n",n);
        return 0;
    }
    int want_add=ref_add(a,b,n),want_sub=ref_sub(a,b,n);
    int got_add=(int)scarry(a,b,n),got_sub=(int)sborrow(a,b,n);
    if(want_add!=got_add || want_sub!=got_sub){
        fprintf(stderr,"overflow flags mismatch for width %d: add %d/%d sub %d/%d\n",
                n,got_add,want_add,got_sub,want_sub);
        return 0;
    }
    return 1;
}
int main(void) {
    for(int x=0;x<256;x++)
        for(int y=0;y<256;y++)
            if(!check((u128)x,(u128)y,1))return 1;
    uint64_t state=UINT64_C(0x8379aef87b541a31);
    for(int n=1;n<=16;n++){
        u128 sign=(u128)1<<(8*n-1);
        const u128 edges[]={0,1,sign-1,sign,sign+1,sign+sign-1,
                            (u128)-1, (u128)INT64_MAX, (u128)INT64_MIN};
        for(unsigned i=0;i<sizeof edges/sizeof *edges;i++)
            for(unsigned j=0;j<sizeof edges/sizeof *edges;j++)
                if(!check(edges[i],edges[j],n))return 2;
        for(int k=0;k<30000;k++){
            u128 a=((u128)next(&state)<<64)|next(&state);
            u128 b=((u128)next(&state)<<64)|next(&state);
            if(!check(a,b,n))return 3;
        }
    }
    puts("Sign extension and signed carry/borrow: exhaustive byte, edges and randomized 1..16-byte widths OK");
    return 0;
}
