from __future__ import print_function

# inspired from test_blfuncs.py

from blaze.blfuncs import BlazeFunc
from blaze.datashape import double, complex128 as c128

import blaze
import blaze.blz as blz

from blaze.datashape import to_numpy
from blaze.datadescriptor import (NumPyDataDescriptor,
                                  BLZDataDescriptor)
from itertools import izip
import numpy as np
import ctypes


########################################################################
#
# Note: this comes from execute_expr_single... but I want to experiment
# with its implementation
#
########################################################################

def execute_expr_single(dd_list, ck_ds_list, ck):
    """
    dd_list : list of data_descriptors (dd[-1] being dst)
    ck_ds_list: list of datashapes expected by the kernel (dd[-1] being dst)
    ck : the kernel to apply

    func: apply the kernel over the sources, place the result in dst.
          dst should be writeable.
    """

    # PRECONDITIONS

    # 1. We have as many datadescriptors as needed by the kernel
    if len(dd_list) != len(ck_ds_list):
        raise ValueError('The length of dd_list and cd_ds_list must match')

    # this is the list of ranks to iterate over for each data decriptor
    rank_list = [len(dd.dshape) - len(ds) for dd, ds in izip (dd_list, ck_ds_list)]

    # 2. Data descriptors should have the ranks expected by the kernel as suffixes
    for dd, ck_ds, rank in izip(dd_list, ck_ds_list, rank_list):
        if dd.dshape.subarray(rank) != ck_ds:
            raise TypeError(('Kernel dshape %s must be a suffix ' +
                            'of data descriptor dshape %s') % (src_ds, src.dshape))

    # 3. Destination should have MUST have the highest rank (should
    # not broadcast on results!). Remember... -1 is dst!
    if rank_list[-1] < max(rank_list):
        raise BroadcastError('Cannot broadcast into' +
                             'a dshape with fewer dimensions')


    #The idea is to iterate over the highest dimensions... 
    ndims = rank_list[-1]

    if ndims == 0:
        pass
    elif ndims == 1:
        pass
    else:
        # recurse
#        gen = ((dd.__iter__() if rank < ndims or len(dd)==1 else (dd for irange(42)))  for dd, rank in izip(dd_list, rank_list))
        execute_expr_single(recurse_dd_list, ck_ds_list, ck)

    SINGLE = 1
    ITER = 2
    src_work_list = []
    # Process all the src argument iterators/elements
    for src, src_ndim in izip(src_list, src_ndim_list):
        if src_ndim < dst_ndim:
            # Broadcast the src data descriptor across
            # the outermost dst dimension
            if dst_ndim == 1:
                # If there's a one-dimensional loop left,
                # use the element interfaces to process it
                se = src.element_reader(0)
                src_ptr = se.read_single(())
                src_work_list.append((SINGLE, src_ptr, se))
            else:
                src_work_list.append((SINGLE, src, None))
        elif src_ndim > dst_ndim:
            assert(False) # This should no longer happen because of PRE.3.
        elif dst_ndim == 0:
            # Call the kernel once
            se = src.element_reader(0)
            src_ptr = se.read_single(())
            src_work_list.append((SINGLE, src_ptr, se))
        else:
            dst_dim_size, src_dim_size = len(dst), len(src)
            if src_dim_size not in [1, dst_dim_size]:
                raise BroadcastError(('Cannot broadcast dimension of ' +
                            'size %d into size %d') % (src_dim_size, dst_dim_size))
            # Broadcast the outermost dimension of src
            # to the outermost dimension of dst
            if dst_ndim == 1:
                # Use the element pointer interfaces for the last dimension
                if src_dim_size == 1:
                    se = src.element_reader(1)
                    src_ptr = se.read_single((0,))
                    src_work_list.append((SINGLE, src_ptr, se))
                else:
                    se = src.element_read_iter()
                    src_work_list.append((ITER, se, None))
            else:
                # Use the Python-level looping constructs
                # for processing higher numbers of dimensions.
                if src_dim_size == 1:
                    src_work_list.append((SINGLE, src[0], None))
                else:
                    src_work_list.append((ITER, src.__iter__(), None))
    # Loop through the outermost dimension
    # Broadcast the src data descriptor across
    # the outermost dst dimension
    if dst_ndim == 0:
        src_ptr_arr = (ctypes.c_void_p * len(src_work_list))()
        for i, (tp, obj, aux) in enumerate(src_work_list):
            src_ptr_arr[i] = ctypes.c_void_p(obj)
        de = dst.element_writer(0)
        with de.buffered_ptr(()) as dst_ptr:
            ck(dst_ptr, ctypes.cast(src_ptr_arr, ctypes.POINTER(ctypes.c_void_p)))
    elif dst_ndim == 1:
        # If there's a one-dimensional loop left,
        # use the element write iter to process
        # it.
        src_ptr_arr = (ctypes.c_void_p * len(src_work_list))()
        with dst.element_write_iter() as de:
            for dst_ptr in de:
                for i, (tp, obj, aux) in enumerate(src_work_list):
                    if tp == SINGLE:
                        src_ptr_arr[i] = ctypes.c_void_p(obj)
                    else:
                        src_ptr_arr[i] = ctypes.c_void_p(next(obj))
                    #print('src ptr', i, ':', hex(src_ptr_arr[i]))
                #print('dst ptr', hex(dst_ptr))
                ck(dst_ptr, src_ptr_arr)
    else:
        # Use the Python-level looping constructs
        # for processing higher numbers of dimensions.
        for dd in dst:
            src_dd_list = []
            for tp, obj, aux in src_work_list:
                if tp == SINGLE:
                    src_dd_list.append(obj)
                else:
                    src_dd_list.append(next(obj))
            execute_expr_single(dd, src_dd_list, dst_ds, src_ds_list, ck)




def _add(a,b):
    return a+b

def _mul(a,b):
    return a*b

add = BlazeFunc('add', [ ('f8(f8,f8)', _add),
                         ('c16(c16,c16)', _add)])
mul = BlazeFunc('mul', {(double,)*3: _mul,
                          (c128,)*3: _mul })


#dummy_add = """
#void d_add(double * result,
#           const double * src1,
#           const double * src2) {
#    *result = *src1 + *src2;
#}
#"""
#
#d_add = BlazeFunc('d_add', [('cpp', dummy_add)])


a = blaze.array([[1,2,3]]*10000,dshape=double)
b = blaze.array([[6,5,4]]*10000,dshape=double)

c = add(a,b)
d = mul(c,c)


# now d contains an array with a data-provider representing the operation 
# (a+b)*(a+b)
# how to build a concrete array containing the results?
def banner(title=None):
    if title is None:
        print("-"*72)
    else:
        print("-- %s %s" %(title, '-'*(68 - len(title))))

banner("func_ptr")
print(d._data.kerneltree.func_ptr)
banner("ctypes_func")
print(d._data.kerneltree.ctypes_func)
banner()


########################################################################
#  Try to get the kernel to execute in the context of the kernel tree  #
########################################################################
def _convert(c_type, ptr, shape):
    b = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_double))
    cs = ctypes.c_ssize_t * len(shape)
    s = cs(*shape)
    return c_type(b,s)


def execute_datadescriptor(dd):
    # make a lifted fused func...
    lifted = dd.kerneltree._fused.kernel.lift(2,'C')
    cf = lifted.ctypes_func
    # the actual ctypes function to call
    args = [(ct._type_, 
            arr.arr._data.element_reader(0).read_single(()),
            arr.arr.dshape.shape) for ct, arr in izip(cf.argtypes[:-1], dd.args)]

    res_dd = NumPyDataDescriptor(np.empty(*to_numpy(dd.dshape)))
    with res_dd.element_writer(0).buffered_ptr(()) as dst_ptr:
        args.append((cf.argtypes[-1]._type_, dst_ptr, res_dd.shape))
        cf_args = [_convert(*foo) for foo in args]
        cf(*[ctypes.byref(x) for x in cf_args])

    return blaze.Array(res_dd)


def execute_datadescriptor_outerdim(dd):
    # only lift by one
    lifted = dd.kerneltree._fused.kernel.lift(1,'C')
    cf = lifted.ctypes_func
    print(dir(cf))
    # element readers for operands
    args = [(ct._type_, 
             arr.arr._data.element_reader(1),
             arr.arr.dshape.shape[1:]) 
            for ct, arr in izip(cf.argtypes[:-1], dd.args)]

    res_dd = NumPyDataDescriptor(np.empty(*to_numpy(dd.dshape)))
    outer_dimension = res_dd.shape[0]
    dst = res_dd.element_writer(1)

    for i in xrange(outer_dimension):
        args_i = [(t, er.read_single((i,)), sh) for t, er, sh in args]
        with dst.buffered_ptr((i,)) as dst_ptr:
            args_i.append((cf.argtypes[-1]._type_, dst_ptr, res_dd.shape[1:]))
            cf_args = [_convert(*foo) for foo in args_i]
            cf(*[ctypes.byref(x) for x in cf_args])

    return blaze.Array(res_dd)

def execute_datadescriptor_ooc(dd, res_name=None):
    # only lift by one
    res_ds = dd.dshape
    res_shape, res_dt = to_numpy(dd.dshape)
    
    lifted = dd.kerneltree._fused.kernel.lift(1,'C')
    cf = lifted.ctypes_func

    # element readers for operands
    args = [(ct._type_, 
             arr.arr._data.element_reader(1),
             arr.arr.dshape.shape[1:]) 
            for ct, arr in izip(cf.argtypes[:-1], dd.args)]

    res_dd = BLZDataDescriptor(blz.zeros((0,) + res_shape[1:],
                                         dtype = res_dt,
                                         rootdir = res_name))

    res_ct = ctypes.c_double*3
    res_buffer = res_ct()
    res_buffer_entry = (cf.argtypes[-1]._type_,
                        ctypes.pointer(res_buffer), 
                        res_shape[1:])
    with res_dd.element_appender() as ea:
        for i in xrange(res_shape[0]):
            args_i = [(t, er.read_single((i,)), sh) 
                      for t, er, sh in args]
            args_i.append(res_buffer_entry)
            cf_args = [_convert(*foo) for foo in args_i]
            cf(*[ctypes.byref(x) for x in cf_args])
            ea.append(ctypes.addressof(res_buffer),1)

    return blaze.Array(res_dd)


res = execute_datadescriptor_ooc(d._data, 'foo.blz')
banner("result")
print(res)

def describe_arg(arg):
    return ("arg arr: %s kind: %s rank: %s llvmtype: %s"
          % (arg.arr, arg.kind, arg.rank, arg.llvmtype))

print('\n'.join([describe_arg(ar) for ar in d._data.args]))

banner()
a_er = a._data.element_reader(0)
print(a_er)
print(a_er.read_single(()))

# it should be something in the lines of...