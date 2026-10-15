"""Offline, numeric-only binary80 rounding reference for ARM64 research.

SLOW exact Fraction arithmetic, NOT a runtime backend. Supports finite normal,
subnormal and zero numbers, CW=0x037f (extended precision, round-nearest-even,
masked). Rejects unsupported, infinity, NaN, other CW, overflow and division
by zero. Does not model SW/C1, tag/TOP, FIP/FDP, faults or exceptions.
"""
from __future__ import annotations
from fractions import Fraction

BIAS=16383

class UnsupportedBinary80(ValueError):
    pass


def unpack(bits:bytes)->tuple[int,int,int]:
    if not isinstance(bits,bytes) or len(bits)!=10:
        raise UnsupportedBinary80("Expected 10-byte binary80 buffer")
    sig=int.from_bytes(bits[:8],"little")
    se=int.from_bytes(bits[8:],"little")
    return se>>15,se&0x7fff,sig


def exact_value(bits:bytes)->Fraction:
    sign,exp,sig=unpack(bits)
    if exp==0x7fff:
        raise UnsupportedBinary80("NaN and infinity need full state")
    if exp and not sig & (1<<63):
        raise UnsupportedBinary80("Unsupported unnormal encoding")
    if exp and not sig:
        raise UnsupportedBinary80("Zero significant with nonzero exponent")
    shift=(exp if exp else 1)-BIAS-63
    x=Fraction(sig<<shift,1) if shift>=0 else Fraction(sig,1<<(-shift))
    return -x if sign else x


def floor_log2(x:Fraction)->int:
    if x<=0:raise ValueError("Expected positive finite magnitude")
    n,d=x.numerator,x.denominator
    e=n.bit_length()-d.bit_length()
    if e>=0:
        if n<d<<e:e-=1
    elif n<<(-e)<d:
        e-=1
    return e


def round_nearest_even(n:int,d:int)->int:
    if n<0 or d<=0:raise ValueError("Expected positive rational")
    q,r=divmod(n,d)
    return q+(2*r>d or (2*r==d and bool(q&1)))


def scaled_round(value:Fraction,shift:int)->int:
    n,d=value.numerator,value.denominator
    return round_nearest_even(n<<shift,d) if shift>=0 else round_nearest_even(n,d<<(-shift))


def encode_finite(value:Fraction,*,sign_zero:int=0)->bytes:
    if not isinstance(value,Fraction):
        raise TypeError("Use exact Fraction rather than host float/double")
    if value==0:
        return (0).to_bytes(8,"little")+(0x8000 if sign_zero else 0).to_bytes(2,"little")
    sign=int(value<0)
    x=abs(value)
    e=floor_log2(x)
    E=e+BIAS
    if E>0x7ffe:
        raise UnsupportedBinary80("Binary80 overflow requires x87 status")
    if E>=1:
        sig=scaled_round(x,63-e)
        if sig==(1<<64):
            sig=1<<63
            E+=1
            if E>0x7ffe:
                raise UnsupportedBinary80("Rounding overflow needs x87 status")
    else:
        sig=scaled_round(x,BIAS+62)
        E=1 if sig>=(1<<63) else 0
    if sig>=(1<<64):
        raise UnsupportedBinary80("Invalid significand")
    return sig.to_bytes(8,"little")+((sign<<15)|E).to_bytes(2,"little")


def operate(op:str,left:bytes,right:bytes,*,cw:int=0x037f)->bytes:
    if cw!=0x037f:
        raise UnsupportedBinary80("Only CW=0x037f is modeled")
    a,b=exact_value(left),exact_value(right)
    if op=="add":r=a+b
    elif op=="sub":r=a-b
    elif op=="mul":r=a*b
    elif op=="div":
        if not b:raise UnsupportedBinary80("Division by zero requires status")
        r=a/b
    else:raise UnsupportedBinary80("Unknown arithmetic opcode")
    sa,_,_=unpack(left)
    sb,_,_=unpack(right)
    zero_sign=(sa^sb) if op in ("mul","div") else 0
    return encode_finite(r,sign_zero=zero_sign)


def to_binary32_bits(value:bytes)->int:
    """Finite binary80->binary32 nearest-even bits, without FPU state."""
    sign,_,_=unpack(value)
    x=abs(exact_value(value))
    if not x:return sign<<31
    e=floor_log2(x)
    E=e+127
    if E>=255:
        raise UnsupportedBinary80("float32 overflow needs status")
    if E>=1:
        sig=scaled_round(x,23-e)
        if sig==(1<<24):
            sig=1<<23
            E+=1
            if E>=255:raise UnsupportedBinary80("float32 rounding overflow")
        return (sign<<31)|(E<<23)|(sig & ((1<<23)-1))
    sig=scaled_round(x,149)
    if sig>=(1<<23):
        return (sign<<31)|(1<<23)
    return (sign<<31)|sig
