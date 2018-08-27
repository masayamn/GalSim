/* -*- c++ -*-
 * Copyright (c) 2012-2018 by the GalSim developers team on GitHub
 * https://github.com/GalSim-developers
 *
 * This file is part of GalSim: The modular galaxy image simulation toolkit.
 * https://github.com/GalSim-developers/GalSim
 *
 * GalSim is free software: redistribution and use in source and binary forms,
 * with or without modification, are permitted provided that the following
 * conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions, and the disclaimer given in the accompanying LICENSE
 *    file.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions, and the disclaimer given in the documentation
 *    and/or other materials provided with the distribution.
 */

#include "PyBind11Helper.h"
#include "Table.h"

namespace galsim {

    static Table* MakeTable(size_t iargs, size_t ivals, int N, const char* interp_c)
    {
        const double* args = reinterpret_cast<double*>(iargs);
        const double* vals = reinterpret_cast<double*>(ivals);
        std::string interp(interp_c);

        Table::interpolant i = Table::linear;
        if (interp == "spline") i = Table::spline;
        else if (interp == "floor") i = Table::floor;
        else if (interp == "ceil") i = Table::ceil;
        else if (interp == "nearest") i = Table::nearest;

        return new Table(args, vals, N, i);
    }

    static void InterpMany(const Table& table, size_t iargs, size_t ivals, int N)
    {
        const double* args = reinterpret_cast<const double*>(iargs);
        double* vals = reinterpret_cast<double*>(ivals);
        table.interpMany(args, vals, N);
    }

    static Table2D* MakeTable2D(size_t ix, size_t iy, size_t ivals, int Nx, int Ny,
                                const char* interp_c)
    {
        const double* x = reinterpret_cast<const double*>(ix);
        const double* y = reinterpret_cast<const double*>(iy);
        const float* vals = reinterpret_cast<const float*>(ivals);
        std::string interp(interp_c);

        Table2D::interpolant i = Table2D::linear;
        if (interp == "floor") i = Table2D::floor;
        else if (interp == "ceil") i = Table2D::ceil;
        else if (interp == "nearest") i = Table2D::nearest;

        return new Table2D(x, y, vals, Nx, Ny, i);
    }

    static void InterpMany2D(const Table2D& table2d, size_t ix, size_t iy, size_t ivals, int N)
    {
        const double* x = reinterpret_cast<const double*>(ix);
        const double* y = reinterpret_cast<const double*>(iy);
        float* vals = reinterpret_cast<float*>(ivals);
        table2d.interpMany(x, y, vals, N);
    }

    static void Gradient(const Table2D& table2d, double x, double y, size_t igrad)
    {
        double* grad = reinterpret_cast<double*>(igrad);
        table2d.gradient(x, y, grad[0], grad[1]);
    }

    static void GradientMany(const Table2D& table2d,
                             size_t ix, size_t iy, size_t idfdx, size_t idfdy, int N)
    {
        const double* x = reinterpret_cast<const double*>(ix);
        const double* y = reinterpret_cast<const double*>(iy);
        double* dfdx = reinterpret_cast<double*>(idfdx);
        double* dfdy = reinterpret_cast<double*>(idfdy);
        table2d.gradientMany(x, y, dfdx, dfdy, N);
    }

    void pyExportTable(PY_MODULE& _galsim)
    {
        py::class_<Table>(GALSIM_COMMA "_LookupTable" BP_NOINIT)
            .def(PY_INIT(&MakeTable))
            .def("interp", &Table::lookup)
            .def("interpMany", &InterpMany);

        py::class_<Table2D >(GALSIM_COMMA "_LookupTable2D" BP_NOINIT)
            .def(PY_INIT(&MakeTable2D))
            .def("interp", &Table2D::lookup)
            .def("interpMany", &InterpMany2D)
            .def("gradient", &Gradient)
            .def("gradientMany", &GradientMany);
    }

} // namespace galsim
