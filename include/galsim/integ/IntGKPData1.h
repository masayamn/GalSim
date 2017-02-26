/* -*- c++ -*-
 * Copyright (c) 2012-2017 by the GalSim developers team on GitHub
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

#ifndef GalSim_IntGKP1_H
#define GalSim_IntGKP1_H

/**
 * @file IntGKPData1.h
 *
 * @brief Gauss-Kronrod-Patterson quadrature coefficients using the 
 *        1-, 3-, 7-, 15-, 31-, 63-, and 127-point rule.
 *
 * The values were calculated by Mike Jarvis using long double precision.
 */

namespace galsim {
namespace integ {

    static const int NGKPLEVELS = 7;

    inline int gkp_n(int level) 
    { 
        assert(level >= 0 && level < NGKPLEVELS);
        static const int ngkp[NGKPLEVELS] = {0,1,2,4,8,16,32};
        return ngkp[level]; 
    }

    template <class T> 
    inline const std::vector<T>& gkp_x(int level)
    {
        static const std::vector<T> vx1(0);

        static const T ax3[1] = {
            0.7745966692414833770358531
        };
        static const std::vector<T> vx3(ax3,ax3+1);

        static const T ax7[2] = {
            0.9604912687080202834235071,
            0.4342437493468025580020715
        };
        static const std::vector<T> vx7(ax7,ax7+2);

        static const T ax15[4] = {
            0.9938319632127550222085128,
            0.8884592328722569988904202,
            0.6211029467372264029406874,
            0.2233866864289668816282040
        };
        static const std::vector<T> vx15(ax15,ax15+4);

        static const T ax31[8] = {
            0.9990981249676675976622261,
            0.9815311495537401068673619,
            0.9296548574297400566701257,
            0.8367259381688687355027538,
            0.7024962064915270786098002,
            0.5313197436443756239721034,
            0.3311353932579768330926408,
            0.1124889431331866257458433
        };
        static const std::vector<T> vx31(ax31,ax31+8);

        static const T ax63[16] = {
            0.9998728881203576119379568,
            0.9972062593722219590764525,
            0.9886847575474294799385289,
            0.9721828747485817965780588,
            0.9463428583734029051484962,
            0.9103711569570042924977907,
            0.8639079381936904771464159,
            0.8069405319502176118563080,
            0.7397560443526947586772178,
            0.6629096600247805954610153,
            0.5771957100520458148436910,
            0.4836180269458410275621533,
            0.3833593241987303469164852,
            0.2777498220218243150653564,
            0.1682352515522074649823133,
            0.05634431304659278997196786
        };
        static const std::vector<T> vx63(ax63,ax63+16);

        static const T ax127[32] = {
            0.9999824303548916002883871,
            0.9995987996719106826208247,
            0.9983166353184073925744239,
            0.9957241046984071885071788,
            0.9914957211781061323986149,
            0.9853714995985203711137519,
            0.9771415146397057141563962,
            0.9666378515584165670922798,
            0.9537300064257611364147486,
            0.9383203977795928836548223,
            0.9203400254700124207298214,
            0.8997448997769400366386332,
            0.8765134144847052697416266,
            0.8506444947683502797578274,
            0.8221562543649804073725271,
            0.7910849337998483614346381,
            0.7574839663805136379262696,
            0.7214230853700989154849762,
            0.6829874310910792280870776,
            0.6422766425097595137741136,
            0.5994039302422428929742510,
            0.5544951326319325488663814,
            0.5076877575337166021547831,
            0.4591300119898323328735020,
            0.4089798212298886724090317,
            0.3574038378315321523762149,
            0.3045764415567140433353240,
            0.2506787303034831766129571,
            0.1958975027111001539154602,
            0.1404242331525601745938196,
            0.08445404008371088371018217,
            0.02818464894974569433939733
        };
        static const std::vector<T> vx127(ax127,ax127+32);

        static const std::vector<T>* x[NGKPLEVELS] = 
        {&vx1,&vx3,&vx7,&vx15,&vx31,&vx63,&vx127};

        assert(level >= 0 && level < NGKPLEVELS);
        return *x[level];
    }

    template <class T> 
    inline const std::vector<T>& gkp_wa(int level)
    {
        static const std::vector<T> vw3a(0);

        static const T aw7a[1] = {
            0.2684880898683334407285693
        };
        static const std::vector<T> vw7a(aw7a,aw7a+1);

        static const T aw15a[3] = {
            0.1344152552437842203599688,
            0.05160328299707973969692012,
            0.2006285293769890210339319
        };
        static const std::vector<T> vw15a(aw15a,aw15a+3);

        static const T aw31a[7] = {
            0.06720775429599070354040106,
            0.02580759809617665356464612,
            0.1003142786117955787712936,
            0.008434565739321106246314930,
            0.04646289326175798654140464,
            0.08575592004999035115418652,
            0.1095784210559246382366884
        };
        static const std::vector<T> vw31a(aw31a,aw31a+7);

        static const T aw63a[15] = {
            0.03360387714820773054173399,
            0.01290380010035126562597665,
            0.05015713930589953741367955,
            0.004217630441558854839084227,
            0.02323144663991026944325649,
            0.04287796002500773449291230,
            0.05478921052796286503221753,
            0.001265156556230068011372609,
            0.008223007957235929669257784,
            0.01797855156812827033289605,
            0.02848975474583354861250609,
            0.03843981024945553203864035,
            0.04681355499062801240264808,
            0.05283494679011651986207666,
            0.05597843651047631940755338
        };
        static const std::vector<T> vw63a(aw63a,aw63a+15);

        static const T aw127a[31] = {
            0.01680193857410386527086942,
            0.006451900050175736922805087,
            0.02507856965294976870683977,
            0.002108815245726632878535242,
            0.01161572331995513472698495,
            0.02143898001250386724645616,
            0.02739460526398143251610877,
            0.0006326073193626332640525769,
            0.004111503978654693047167841,
            0.008989275784064135723280604,
            0.01424487737291677430634157,
            0.01921990512472776601932028,
            0.02340677749531400620132404,
            0.02641747339505825993103833,
            0.02798921825523815970377669,
            0.0001807395644453909103150119,
            0.001289524082610417407932182,
            0.003057753410175531136173120,
            0.005249123454808859125133999,
            0.007703375233279741848165979,
            0.01029711695795635552368646,
            0.01293483966360737345473396,
            0.01553677555584398243992842,
            0.01803221639039128632005310,
            0.02035775505847215946694702,
            0.02245726582681609870712712,
            0.02428216520333659935797356,
            0.02579162697602422938840455,
            0.02695274966763303196343848,
            0.02774070217827968199391920,
            0.02813884991562715063629767
        };
        static const std::vector<T> vw127a(aw127a,aw127a+31);

        static const std::vector<T>* wa[NGKPLEVELS] = 
        {0,&vw3a,&vw7a,&vw15a,&vw31a,&vw63a,&vw127a};

        assert(level >= 1 && level < NGKPLEVELS);
        return *wa[level];
    }

    template <class T> 
    inline const std::vector<T>& gkp_wb(int level)
    {
        static const T aw1b[1] = {
            2.000000000000000000000000
        };
        static const std::vector<T> vw1b(aw1b,aw1b+1);

        static const T aw3b[2] = {
            0.5555555555555555555555556,
            0.8888888888888888888888889
        };
        static const std::vector<T> vw3b(aw3b,aw3b+2);

        static const T aw7b[3] = {
            0.1046562260264672651938239,
            0.4013974147759622229050518,
            0.4509165386584741423451101
        };
        static const std::vector<T> vw7b(aw7b,aw7b+3);

        static const T aw15b[5] = {
            0.01700171962994026033902742,
            0.09292719531512453768589422,
            0.1715119091363913807873532,
            0.2191568584015874964036932,
            0.2255104997982066873864225
        };
        static const std::vector<T> vw15b(aw15b,aw15b+5);

        static const T aw31b[9] = {
            0.002544780791561874415402782,
            0.01644604985438781093378839,
            0.03595710330712932209677783,
            0.05697950949412335741219737,
            0.07687962049900353104270519,
            0.09362710998126447361665878,
            0.1056698935802348097438159,
            0.1119568730209534568801436,
            0.1127552567207686916071499
        };
        static const std::vector<T> vw31b(aw31b,aw31b+9);

        static const T aw63b[17] = {
            0.0003632214818455306596935806,
            0.002579049794685688272427796,
            0.006115506822117246339678284,
            0.01049824690962132189827284,
            0.01540675046655949780213083,
            0.02059423391591271114918856,
            0.02586967932721474691075827,
            0.03107355111168796487988439,
            0.03606443278078257264010716,
            0.04071551011694431893389410,
            0.04491453165363219741425425,
            0.04856433040667319871594712,
            0.05158325395204845877680910,
            0.05390549933526606392687695,
            0.05548140435655936398783841,
            0.05627769983125430127259535,
            0.05637762836038471738766256
        };
        static const std::vector<T> vw63b(aw63b,aw63b+17);

        static const T aw127b[33] = {
            0.00005053609520786089516638322,
            0.0003777466463269839352971478,
            0.0009383698485423815640378046,
            0.001681142865421469902932108,
            0.002568764943794020373297319,
            0.003572892783517299649375536,
            0.004671050372114321747405966,
            0.005843449875835639507559476,
            0.007072489995433555468046319,
            0.008342838753968157705584124,
            0.009641177729702536695298303,
            0.01095573338783790164803273,
            0.01227583056008277008696633,
            0.01359157100976554678957292,
            0.01489364166481518203481040,
            0.01617321872957771994194796,
            0.01742193015946417374715226,
            0.01863184825613879018631404,
            0.01979549504809749948802772,
            0.02090585144581202385222185,
            0.02195636630531782493926050,
            0.02294096422938774876080053,
            0.02385405210603854008044603,
            0.02469052474448767690906084,
            0.02544576996546476581257440,
            0.02611567337670609768049881,
            0.02669662292745035990615470,
            0.02718551322962479181920860,
            0.02757974956648187303486871,
            0.02787725147661370160852380,
            0.02807645579381724660684785,
            0.02817631903301660213065358,
            0.02818881418019235869383128
        };
        static const std::vector<T> vw127b(aw127b,aw127b+33);

        static const std::vector<T>* wb[NGKPLEVELS] = 
        {&vw1b,&vw3b,&vw7b,&vw15b,&vw31b,&vw63b,&vw127b};

        assert(level >= 0 && level < NGKPLEVELS);
        return *wb[level];
    }

}
}

#endif
