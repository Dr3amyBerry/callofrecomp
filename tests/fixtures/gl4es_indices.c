/*
GL4ES array.c normalization fixture, revision ec16bedd8819c475326f4f1a3063772c6d986e06
https://github.com/ptitSeb/gl4es

Copyright (c) 2016-2018 Sebastien Chevalier
Copyright (c) 2013-2016 Ryan Hileman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/
void getminmax_indices_us(const GLushort *indices, GLsizei *max, GLsizei *min, GLsizei count) {
    if (!count) return;
    *max = indices[0];
    *min = indices[0];
    for (int i = 1; i < count; i++) {
        GLsizei n = indices[i];
        if( n < *min) *min = n;
        if (n > *max) *max = n;
    }
}
void normalize_indices_us(GLushort *indices, GLsizei *max, GLsizei *min, GLsizei count) {
    getminmax_indices_us(indices, max, min, count);
    for (int i = 0; i < count; i++) {
        indices[i] -= *min;
    }
}
void getminmax_indices_ui(const GLuint *indices, GLsizei *max, GLsizei *min, GLsizei count) {
    if (!count) return;
    *max = indices[0];
    *min = indices[0];
    for (int i = 1; i < count; i++) {
        GLsizei n = indices[i];
        if( n < *min) *min = n;
        if (n > *max) *max = n;
    }
}
void normalize_indices_ui(GLuint *indices, GLsizei *max, GLsizei *min, GLsizei count) {
    getminmax_indices_ui(indices, max, min, count);
    for (int i = 0; i < count; i++) {
        indices[i] -= *min;
    }
}
